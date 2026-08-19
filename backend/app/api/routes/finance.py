import io
import zipfile
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.internal_performance_certificate import (
    KIHAGYVA,
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.models.performance_certificate import (
    PerformanceCertificate,
    PerformanceCertificateInvoice,
    PerformanceCertificateTetel,
)
from app.models.project_code import ProjectCode
from app.services import document_storage, elszamolas, kiadas_kapcsolatok
from app.services.hu_datum import belsos_tig_honapja, ev_honap_szoveg
from app.services.portal_storage import R2NotConfiguredError
from app.schemas.finance import (
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    KpForgalomCreate,
    KpForgalomRead,
    KpForgalomUpdate,
    RevenueCreate,
    RevenueRead,
    RevenueUpdate,
)


def _kiadas_torles_elott(expense: Expense, db: Session) -> None:
    """Egy kiadás akkor is törölhető legyen, ha van hozzá kapcsolódó rekord.

    A TIG "kifizetve" jelölése hozza létre ezt a sort, tehát a törlésének
    éppen az a jelentése, hogy MÉGSEM fizettük ki - ilyenkor az érintett papír
    visszakerül "nincs kifizetve" állapotba, és újra teendő lesz. Enélkül a
    tévesen felvezetett kifizetés visszavonhatatlan volt: a kiadást a TIG
    hivatkozása, a TIG-et pedig a kifizetettsége védte
    (lásd services/kiadas_kapcsolatok.py)."""
    kiadas_kapcsolatok.bontsd_le_a_kapcsolatokat(expense, db)


expenses_router = build_crud_router(
    model=Expense,
    create_schema=ExpenseCreate,
    update_schema=ExpenseUpdate,
    read_schema=ExpenseRead,
    prefix="/expenses",
    tags=["finance"],
    page="/penzugyek",
    before_delete=_kiadas_torles_elott,
)

revenues_router = build_crud_router(
    model=Revenue,
    create_schema=RevenueCreate,
    update_schema=RevenueUpdate,
    read_schema=RevenueRead,
    prefix="/revenues",
    tags=["finance"],
    page="/penzugyek",
)

kp_forgalom_router = build_crud_router(
    model=KpForgalom,
    create_schema=KpForgalomCreate,
    update_schema=KpForgalomUpdate,
    read_schema=KpForgalomRead,
    prefix="/kp-forgalom",
    tags=["finance"],
    page="/penzugyek",
)

summary_router = APIRouter(prefix="/finance", tags=["finance"])

PENZUGY_PAGE = "/penzugyek"


class MonthlyFinance(BaseModel):
    month: str
    bevetel: float
    kiadas: float


class OutstandingProject(BaseModel):
    project_code_id: int
    projektkod: str
    ugyfel_nev: str | None
    kintlevo_osszeg: float
    legkorabbi_hatarido: date | None
    lejart: bool


class PaymentMethodBreakdown(BaseModel):
    kifizetes_modja: str | None
    osszeg: float


class FinanceSummary(BaseModel):
    """Az összesítő számai NETTÓBAN értendők (lásd services/elszamolas.py):
    az ÁFA átfolyó tétel, két oldal bruttó összevetéséből nem profit jön ki,
    hanem az ÁFA-tartalmak különbsége.

    A bruttó ettől még látszik - de külön, `_brutto` végű mezőkben, mert arra
    is szükség van: az megy ki (és jön be) a bankszámlán."""

    ytd_bevetel: float
    ytd_kiadas: float
    ytd_profit: float
    #: Ugyanaz az időszak bruttóban - tájékoztatásul, a tényleges pénzmozgás.
    ytd_bevetel_brutto: float
    ytd_kiadas_brutto: float
    osszes_kintlevoseg: float
    kintlevo_projektek_szama: int
    havi_trend: list[MonthlyFinance]
    kintlevo_projektek: list[OutstandingProject]
    ytd_kiadas_fizetesi_mod_szerint: list[PaymentMethodBreakdown]


# Egy kiadás csak akkor számít bele a Pénzügy összesítőkbe (YTD kiadás, havi
# trend, fizetési mód szerinti bontás), ha a "Hozzá adás a kiadásokhoz"
# checkbox nincs kifejezetten kikapcsolva - a régi Notion-import forrásai
# (sima "Kiadások" / "Belsős extra kiadások" táblák) nem is ismerték ezt a
# mezőt, ott NULL-ként importálódott, ezért a NULL-t "számítson bele"-ként
# kezeljük (nem "nincs bepipálva"-ként), hogy a checkbox bevezetése ne
# tüntessen el némán történeti kiadásokat az összesítőkből - csak a
# kifejezetten (a "Projekt kiadások" felvitelnél) kipipálatlanul hagyott
# sorok esnek ki. A projektkód-szintű költség (ProjectCode.osszes_koltseg)
# ettől függetlenül MINDIG az adott projekt teljes, valós költségét mutatja -
# ez a gate csak a globális Pénzügy nézetet szűri.
_EXPENSE_COUNTS_TOWARD_TOTALS = Expense.hozzaadas_a_kiadasokhoz.is_not(False)


def _last_n_months(today: date, n: int) -> list[tuple[int, int]]:
    """[(év, hónap), ...] a mai hónapig bezárólag, régitől az újig rendezve -
    ugyanaz a helper, mint a dashboard.py revenue_trend-jénél."""
    months = []
    year, month = today.year, today.month
    for _ in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


@summary_router.get("/summary", response_model=FinanceSummary)
def finance_summary(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A Pénzügyek oldal nagy összesítője: éves (YTD) bevétel/kiadás/profit,
    az utolsó 12 hónap bevétel+kiadás trendje, és a kintlévőségek (kifizetetlen
    bevétel-sorok, azaz Revenue.fizetes_datuma IS NULL) project code-onként
    összesítve, a legnagyobb összeggel elöl."""
    today = date.today()
    year_start = date(today.year, 1, 1)

    # Az összegzés NETTÓBAN megy - bevételnél és kiadásnál ugyanúgy, különben a
    # profit a két oldal ÁFA-tartalmának különbségével csúszna el (lásd
    # services/elszamolas.py). A bruttót külön kérdezzük le, tájékoztatásul.
    ytd_bevetel = (
        db.scalar(
            select(func.coalesce(func.sum(elszamolas.netto_sql(Revenue)), 0)).where(
                Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= year_start
            )
        )
        or 0
    )
    ytd_bevetel_brutto = (
        db.scalar(
            select(func.coalesce(func.sum(elszamolas.brutto_sql(Revenue)), 0)).where(
                Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= year_start
            )
        )
        or 0
    )
    ytd_kiadas = (
        db.scalar(
            select(func.coalesce(func.sum(elszamolas.netto_sql(Expense)), 0)).where(
                Expense.fizetes_datuma.is_not(None),
                Expense.fizetes_datuma >= year_start,
                _EXPENSE_COUNTS_TOWARD_TOTALS,
            )
        )
        or 0
    )
    ytd_kiadas_brutto = (
        db.scalar(
            select(func.coalesce(func.sum(elszamolas.brutto_sql(Expense)), 0)).where(
                Expense.fizetes_datuma.is_not(None),
                Expense.fizetes_datuma >= year_start,
                _EXPENSE_COUNTS_TOWARD_TOTALS,
            )
        )
        or 0
    )

    months = _last_n_months(today, 12)
    min_year, min_month = months[0]
    min_date = date(min_year, min_month, 1)

    revenue_by_month: dict[tuple[int, int], float] = {}
    for row in db.execute(
        select(
            extract("year", Revenue.fizetes_datuma).label("y"),
            extract("month", Revenue.fizetes_datuma).label("m"),
            func.coalesce(func.sum(elszamolas.netto_sql(Revenue)), 0).label("total"),
        )
        .where(Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= min_date)
        .group_by("y", "m")
    ).all():
        revenue_by_month[(int(row.y), int(row.m))] = float(row.total)

    expense_by_month: dict[tuple[int, int], float] = {}
    for row in db.execute(
        select(
            extract("year", Expense.fizetes_datuma).label("y"),
            extract("month", Expense.fizetes_datuma).label("m"),
            func.coalesce(func.sum(elszamolas.netto_sql(Expense)), 0).label("total"),
        )
        .where(Expense.fizetes_datuma.is_not(None), Expense.fizetes_datuma >= min_date, _EXPENSE_COUNTS_TOWARD_TOTALS)
        .group_by("y", "m")
    ).all():
        expense_by_month[(int(row.y), int(row.m))] = float(row.total)

    ytd_kiadas_fizetesi_mod_szerint = [
        PaymentMethodBreakdown(kifizetes_modja=row.kifizetes_modja, osszeg=float(row.total))
        for row in db.execute(
            select(Expense.kifizetes_modja, func.coalesce(func.sum(elszamolas.netto_sql(Expense)), 0).label("total"))
            .where(Expense.fizetes_datuma.is_not(None), Expense.fizetes_datuma >= year_start, _EXPENSE_COUNTS_TOWARD_TOTALS)
            .group_by(Expense.kifizetes_modja)
            .order_by(func.sum(elszamolas.netto_sql(Expense)).desc())
        ).all()
    ]

    havi_trend = [
        MonthlyFinance(
            month=f"{y:04d}-{m:02d}",
            bevetel=revenue_by_month.get((y, m), 0.0),
            kiadas=expense_by_month.get((y, m), 0.0),
        )
        for y, m in months
    ]

    unpaid = db.scalars(
        select(Revenue)
        .where(Revenue.fizetes_datuma.is_(None))
        .options(selectinload(Revenue.project_code).selectinload(ProjectCode.client))
    ).all()

    by_project: dict[int, list[Revenue]] = {}
    for r in unpaid:
        by_project.setdefault(r.project_code_id, []).append(r)

    kintlevo_projektek: list[OutstandingProject] = []
    for pc_id, rows in by_project.items():
        pc = rows[0].project_code
        # A kintlévőség is nettóban - ugyanaz a szám, ami a projekt bevételében
        # és a profitjában szerepel (lásd services/elszamolas.py).
        osszeg = float(sum(elszamolas.osszeg(r) for r in rows))
        hataridok = [r.fizetes_hatarideje for r in rows if r.fizetes_hatarideje]
        legkorabbi = min(hataridok) if hataridok else None
        kintlevo_projektek.append(
            OutstandingProject(
                project_code_id=pc_id,
                projektkod=pc.projektkod if pc else f"#{pc_id}",
                ugyfel_nev=pc.client.nev if pc and pc.client else None,
                kintlevo_osszeg=osszeg,
                legkorabbi_hatarido=legkorabbi,
                lejart=bool(legkorabbi and legkorabbi < today),
            )
        )
    kintlevo_projektek.sort(key=lambda p: p.kintlevo_osszeg, reverse=True)
    osszes_kintlevoseg = sum(p.kintlevo_osszeg for p in kintlevo_projektek)

    return FinanceSummary(
        ytd_bevetel=float(ytd_bevetel),
        ytd_kiadas=float(ytd_kiadas),
        ytd_profit=float(ytd_bevetel) - float(ytd_kiadas),
        ytd_bevetel_brutto=float(ytd_bevetel_brutto),
        ytd_kiadas_brutto=float(ytd_kiadas_brutto),
        osszes_kintlevoseg=osszes_kintlevoseg,
        kintlevo_projektek_szama=len(kintlevo_projektek),
        havi_trend=havi_trend,
        kintlevo_projektek=kintlevo_projektek[:15],
        ytd_kiadas_fizetesi_mod_szerint=ytd_kiadas_fizetesi_mod_szerint,
    )


# --- Kimenő számla fájl + havi számla-csomag -------------------------------


@summary_router.post("/revenues/{revenue_id}/szamla", response_model=RevenueRead)
async def upload_kimeno_szamla(
    revenue_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PENZUGY_PAGE, "edit")),
):
    """A KIMENŐ (megrendelői) számla PDF-jének feltöltése egy bevétel-sorhoz.
    Maga a számla külső számlázó rendszerben készül - ide azért kerül fel, hogy
    a havi könyvelési csomagban (lásd szamlak_zip) a kimenő számlák is benne
    legyenek, ne csak a bejövők. Bevételenként egy fájl: az újabb feltöltés
    lecseréli a korábbit."""
    revenue = db.get(Revenue, revenue_id)
    if revenue is None:
        raise HTTPException(status_code=404, detail="Bevétel nem található")

    data = await file.read()
    kulcs = f"kimeno-szamla/{revenue_id}/{uuid4().hex}_{file.filename}"
    try:
        url = document_storage.upload_bytes(data, kulcs, file.content_type or "application/octet-stream")
    except R2NotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # A korábbi fájl helyét felszabadítjuk - egy bevételhez egy számla tartozik.
    if revenue.szamla_storage_key:
        try:
            document_storage.delete_object(revenue.szamla_storage_key)
        except Exception:  # noqa: BLE001 - a törlés hibája ne bukjon a feltöltésen
            pass

    revenue.szamla_filename = file.filename
    revenue.szamla_storage_key = kulcs
    revenue.szamla_file_url = url
    db.commit()
    db.refresh(revenue)
    return revenue


@summary_router.delete("/revenues/{revenue_id}/szamla", response_model=RevenueRead)
def delete_kimeno_szamla(
    revenue_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PENZUGY_PAGE, "delete")),
):
    revenue = db.get(Revenue, revenue_id)
    if revenue is None:
        raise HTTPException(status_code=404, detail="Bevétel nem található")
    if revenue.szamla_storage_key:
        try:
            document_storage.delete_object(revenue.szamla_storage_key)
        except Exception:  # noqa: BLE001
            pass
    revenue.szamla_filename = None
    revenue.szamla_storage_key = None
    revenue.szamla_file_url = None
    db.commit()
    db.refresh(revenue)
    return revenue


def _honap_szuro(datum: date | None, ev: int, honap: int) -> bool:
    return datum is not None and datum.year == ev and datum.month == honap


def _csatolt_szamlak(db: Session, ev: int, honap: int) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    """A rekordokhoz csatolt (feltöltött vagy Notionból átemelt) SZÁMLA
    kategóriájú fájlok a hónapra bontva: (bejövő, kimenő, leírássorok).

    A hónapot nem a feltöltés ideje adja, hanem a számla mögötti pénzügyi
    dátum - a Notion importból származó fájlok mind egyszerre kerültek fel, a
    hozzájuk tartozó kiadás/bevétel viszont tudja, mikori. Ha nincs ilyen
    dátum, marad a feltöltés napja."""
    bejovo: list[tuple[str, str]] = []
    kimeno: list[tuple[str, str]] = []
    leiras: list[str] = []

    csatolmanyok = db.scalars(
        select(DocumentAttachment).where(DocumentAttachment.kategoria == "szamla")
    ).all()
    kiadasok = {k.id: k for k in db.scalars(select(Expense)).all()} if csatolmanyok else {}
    bevetelek = {b.id: b for b in db.scalars(select(Revenue)).all()} if csatolmanyok else {}

    for csatolmany in csatolmanyok:
        feltoltve = csatolmany.created_at.date() if csatolmany.created_at else None
        datum, forras = feltoltve, f"{csatolmany.entity_type} #{csatolmany.entity_id}"
        if csatolmany.entity_type == "expense":
            kiadas = kiadasok.get(csatolmany.entity_id)
            if kiadas is not None:
                datum = kiadas.fizetes_datuma or kiadas.kiadas_datuma or kiadas.fizetes_hatarideje or feltoltve
                forras = f"Kiadás #{kiadas.id} – {kiadas.megnevezes}"
        elif csatolmany.entity_type == "revenue":
            bevetel = bevetelek.get(csatolmany.entity_id)
            if bevetel is not None:
                datum = bevetel.szamla_kiallitva_datuma or bevetel.fizetes_datuma or feltoltve
                forras = f"Bevétel #{bevetel.id}"
        if not _honap_szuro(datum, ev, honap):
            continue
        mappa = "kimeno" if csatolmany.entity_type == "revenue" else "bejovo"
        nev = f"{csatolmany.entity_type}_{csatolmany.entity_id}_{csatolmany.id}_{csatolmany.filename}"
        (kimeno if mappa == "kimeno" else bejovo).append((nev, csatolmany.storage_key))
        leiras.append(f"{mappa}/{nev}\t{forras}\tdátum: {datum}")

    return bejovo, kimeno, leiras


@summary_router.get("/szamlak-zip")
def szamlak_zip(
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PENZUGY_PAGE, "view")),
):
    """Egy hónap ÖSSZES számlája egyetlen ZIP-ben - a könyvelésnek szánt
    csomag, hogy ne kelljen egyenként végigkattintani a TIG-eket és a
    bevételeket.

    A ZIP két mappára oszlik:

      bejovo/  - a külsős és belsős TIG-ekhez feltöltött (alvállalkozói)
                 számlák, a FELTÖLTÉS hónapja szerint: ekkor érkezett be a
                 számla a rendszerbe,
      kimeno/  - a bevételekhez feltöltött megrendelői számlák, a SZÁMLA
                 KIÁLLÍTÁSÁNAK hónapja szerint (ha nincs kiállítási dátum, a
                 feltöltés hónapja szerint).

    A csomag mellé kerül egy tartalom.txt is, amiben soronként látszik, melyik
    fájl honnan jött - hogy a könyvelő utólag is vissza tudja fejteni."""
    bejovo: list[tuple[str, str]] = []  # (fájlnév a ZIP-ben, storage kulcs)
    leiras: list[str] = []

    kulsos = (
        db.query(PerformanceCertificateInvoice)
        .options(selectinload(PerformanceCertificateInvoice.certificate))
        .all()
    )
    for szamla in kulsos:
        if not _honap_szuro(szamla.created_at.date() if szamla.created_at else None, ev, honap):
            continue
        cert = szamla.certificate
        nev = f"kulsos_tig_{cert.employee_id if cert else 'ismeretlen'}_{szamla.id}_{szamla.filename}"
        bejovo.append((nev, szamla.storage_key))
        leiras.append(f"bejovo/{nev}\tKülsős TIG #{szamla.certificate_id}\tfeltöltve: {szamla.created_at:%Y-%m-%d}")

    belsos = (
        db.query(InternalPerformanceCertificateInvoice)
        .options(selectinload(InternalPerformanceCertificateInvoice.certificate))
        .all()
    )
    for szamla in belsos:
        if not _honap_szuro(szamla.created_at.date() if szamla.created_at else None, ev, honap):
            continue
        cert = szamla.certificate
        honap_jel = "-".join(f"{r:02d}" for r in _belsos_honap(cert)) if cert else "ismeretlen"
        nev = f"belsos_tig_{honap_jel}_{szamla.id}_{szamla.filename}"
        bejovo.append((nev, szamla.storage_key))
        leiras.append(f"bejovo/{nev}\tBelsős TIG ({honap_jel})\tfeltöltve: {szamla.created_at:%Y-%m-%d}")

    kimeno: list[tuple[str, str]] = []
    for revenue in db.scalars(select(Revenue).where(Revenue.szamla_storage_key.is_not(None))):
        datum = revenue.szamla_kiallitva_datuma or (revenue.created_at.date() if revenue.created_at else None)
        if not _honap_szuro(datum, ev, honap):
            continue
        nev = f"bevetel_{revenue.id}_{revenue.szamla_filename or 'szamla.pdf'}"
        kimeno.append((nev, revenue.szamla_storage_key))
        leiras.append(f"kimeno/{nev}\tBevétel #{revenue.id}\tkiállítva: {datum}")

    # A rekordokhoz csatolt számlák (kézzel feltöltve vagy Notionból átemelve).
    csatolt_bejovo, csatolt_kimeno, csatolt_leiras = _csatolt_szamlak(db, ev, honap)
    bejovo += csatolt_bejovo
    kimeno += csatolt_kimeno
    leiras += csatolt_leiras

    if not bejovo and not kimeno:
        raise HTTPException(status_code=404, detail=f"Nincs feltöltött számla erre a hónapra: {ev}. {honap}.")

    buffer = io.BytesIO()
    hibas: list[str] = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for mappa, tetelek in (("bejovo", bejovo), ("kimeno", kimeno)):
            for nev, kulcs in tetelek:
                try:
                    zf.writestr(f"{mappa}/{nev}", document_storage.download_bytes(kulcs))
                except R2NotConfiguredError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                except Exception as exc:  # noqa: BLE001
                    # Egyetlen hiányzó fájl ne buktassa az egész csomagot - a
                    # tartalom.txt-ben viszont látszania kell, mi maradt ki.
                    hibas.append(f"{mappa}/{nev}\tNEM SIKERÜLT LETÖLTENI: {exc}")
        tartalom = [
            f"HYPE OS - {ev}. {honap:02d}. havi számlák",
            "",
            "A 'bejovo' mappa a TIG-ekhez feltöltött (alvállalkozói) számlákat tartalmazza,",
            "a feltöltés hónapja szerint. A 'kimeno' mappa a bevételekhez feltöltött",
            "megrendelői számlákat, a számla kiállításának hónapja szerint.",
            "",
            *leiras,
        ]
        if hibas:
            tartalom += ["", "HIÁNYZÓ FÁJLOK:", *hibas]
        zf.writestr("tartalom.txt", "\n".join(tartalom))

    buffer.seek(0)
    fajlnev = f"szamlak_{ev}_{honap:02d}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fajlnev}"'},
    )


# --- Utalásra váró számlák --------------------------------------------------
#
# Ami már megérkezett hozzánk számlaként, de még nem utaltuk el. Három helyről
# jön össze - a felület egyben mutatja őket, hogy az utalási körnél ne kelljen
# három listát végigkattintani, és a kijelöltek számlái egyetlen ZIP-ben
# letölthetők legyenek (azt viszi a könyvelő/ügyintéző a banki utaláshoz).


#: A projektkód "Számla státusza" értékei, amik azt jelentik: A MEGRENDELŐ MÁR
#: KIFIZETETT MINKET. A Notionból ez az érték jön át (lásd
#: notion_import/importers.py import_project_codes) - a kis/nagybetűtől és a
#: pontos megfogalmazástól függetlenül a "kifizet" szórészlet dönt, hogy egy
#: átfogalmazott állapotnév ne csendben ejtse ki a sort a listából.
KIFIZETETT_STATUSZ_MINTA = "kifizet"

#: A fedezettség lehetséges állapotai (lásd _fedezettseg).
FEDEZETT = "fedezett"
RESZBEN_FEDEZETT = "reszben"
FEDEZETRE_VAR = "var"
NINCS_PROJEKTKOD = "nincs_projektkod"


class UtalasraVaroTetel(BaseModel):
    #: "expense:12" / "kulsos_tig:3" / "belsos_tig:7" - a ZIP-kérésben ezt
    #: küldi vissza a felület, így egyetlen listában kezelhető a három forrás.
    kulcs: str
    tipus: str
    megnevezes: str
    kinek: str | None = None
    osszeg: float | None = None
    penznem: str = "HUF"
    hatarido: date | None = None
    szamla_db: int = 0
    #: Hova visz a sor a felületen (a tétel saját adatlapja).
    link: str | None = None
    #: Megjött-e a tétel FEDEZETE, azaz kifizette-e már a megrendelő azt a
    #: projektkódot, amihez a tétel tartozik. Ettől függ, hogy elutalható-e:
    #: "fedezett" | "reszben" | "var" | "nincs_projektkod" (lásd _fedezettseg).
    fedezettseg: str = NINCS_PROJEKTKOD
    #: A tételhez tartozó projektkódok. Több is lehet: egy havi belsős TIG
    #: több projekt extráit vonja össze - ilyenkor csak akkor utalható
    #: nyugodtan, ha MINDEGYIK kódot kifizették.
    projektkodok: list[str] = []
    #: Ezek közül melyek NINCSENEK még kifizetve (ezekre várunk).
    fedezetlen_projektkodok: list[str] = []


class UtalasraVaroKeres(BaseModel):
    kulcsok: list[str]


def _belsos_honap(tig) -> tuple[int, int]:
    """Egy belsős TIG elszámolt hónapja a dátumaiból - ezzel nevezzük meg."""
    return belsos_tig_honapja(
        tig.ev, tig.honap, tig.teljesites_datuma, tig.fizetesi_hatarido, tig.utalas_datuma
    )


def _szamla_csatolmanyok(db: Session, entity_type: str, entity_ids: list[int]) -> dict[int, list[DocumentAttachment]]:
    """Rekordonként a SZÁMLA kategóriájú csatolmányok (feltöltve vagy Notionból
    átemelve) - ez az, ami az utaláshoz kell."""
    if not entity_ids:
        return {}
    sorok = db.scalars(
        select(DocumentAttachment).where(
            DocumentAttachment.entity_type == entity_type,
            DocumentAttachment.entity_id.in_(entity_ids),
            DocumentAttachment.kategoria == "szamla",
        )
    ).all()
    eredmeny: dict[int, list[DocumentAttachment]] = {}
    for sor in sorok:
        eredmeny.setdefault(sor.entity_id, []).append(sor)
    return eredmeny


def _projektkod_fedezet(db: Session) -> tuple[dict[int, str], set[int]]:
    """(projektkód id -> kód szövege, a KIFIZETETT projektkódok id-jai).

    Kifizetett az a projektkód, amelyiknél
      - a számla státusza szerint már befolyt a pénz ("Kifizetve és számla
        feltöltve" - lásd KIFIZETETT_STATUSZ_MINTA), VAGY
      - a rendszerben rögzített ÖSSZES bevételének van fizetési dátuma.

    A második azért kell, mert a státuszt a Notionban tartják karban, a
    bevétel-sorokat viszont itt: ha az egyiket vezetik, a másikat nem, attól
    még megjött a pénz. A "mind" szándékosan szigorú: ha egy projektkód három
    számlájából csak kettő érkezett meg, a fedezet még nem teljes."""
    kodok = {pc.id: pc.projektkod for pc in db.scalars(select(ProjectCode)).all()}
    statusz_szerint = {
        pc.id
        for pc in db.scalars(select(ProjectCode)).all()
        if KIFIZETETT_STATUSZ_MINTA in (pc.szamla_statusza or "").lower()
    }

    osszes: dict[int, int] = {}
    fizetett: dict[int, int] = {}
    for project_code_id, fizetes_datuma in db.execute(
        select(Revenue.project_code_id, Revenue.fizetes_datuma)
    ).all():
        osszes[project_code_id] = osszes.get(project_code_id, 0) + 1
        if fizetes_datuma is not None:
            fizetett[project_code_id] = fizetett.get(project_code_id, 0) + 1
    bevetel_szerint = {kod for kod, db_szam in osszes.items() if fizetett.get(kod, 0) == db_szam}

    return kodok, statusz_szerint | bevetel_szerint


def _fedezettseg(
    projektkod_idk: list[int], kodok: dict[int, str], kifizetett: set[int]
) -> tuple[str, list[str], list[str]]:
    """(állapot, minden projektkód, a még fedezetlenek) egy tételhez.

    Projektkód nélkül nem tudjuk eldönteni (ilyen a projekthez nem kötött
    kiadás, vagy az a havi belsős TIG, aminek egyetlen tétele sincs kódhoz
    rendelve) - ezeket nem soroljuk sem az utalhatók, sem a várakozók közé,
    hanem külön mutatjuk, hogy látszódjon: itt kézzel kell dönteni."""
    egyediek = list(dict.fromkeys(projektkod_idk))
    if not egyediek:
        return NINCS_PROJEKTKOD, [], []
    minden = [kodok.get(i) or f"#{i}" for i in egyediek]
    fedezetlen = [kodok.get(i) or f"#{i}" for i in egyediek if i not in kifizetett]
    if not fedezetlen:
        return FEDEZETT, minden, []
    if len(fedezetlen) < len(egyediek):
        return RESZBEN_FEDEZETT, minden, fedezetlen
    return FEDEZETRE_VAR, minden, fedezetlen


def _utalasra_varo_tetelek(db: Session) -> list[tuple[UtalasraVaroTetel, list[tuple[str, str]]]]:
    """(tétel, [(fájlnév a ZIP-ben, tárhely-kulcs)]) párok.

    "Utalásra vár" az, ami még nincs kifizetve:
      - kiadás, ami nincs késznek jelölve, nincs fizetési dátuma, és VAN
        feltöltött számlája (enélkül utalni sem tudnánk mi alapján),
      - külsős TIG, aminek van számlája, de nincs kifizetettként jelölve,
      - MINDEN belsős TIG, aminek van összege és nem kihagyott hónap - ehhez
        se számla, se elkészült állapot nem kell: a bért mindig rögtön
        utaljuk.

    A kiadásokhoz és a külsős TIG-ekhez kiszámoljuk a FEDEZETTSÉGET is: megjött-e
    már a pénz arra a projektkódra, amihez tartozik (lásd _fedezettseg) - ebből
    látszik, kinek mehet nyugodtan az utalás. A belsős TIG ebből kimarad: a bér
    nem a megrendelő pénzéből megy, tehát sosem vár fedezetre."""
    eredmeny: list[tuple[UtalasraVaroTetel, list[tuple[str, str]]]] = []
    kodok, kifizetett = _projektkod_fedezet(db)

    kiadasok = list(
        db.scalars(
            select(Expense).where(Expense.kesz.is_(False), Expense.fizetes_datuma.is_(None))
        ).all()
    )
    csatolmanyok = _szamla_csatolmanyok(db, "expense", [k.id for k in kiadasok])
    munkatarsak = {
        e.id: e.full_name
        for e in db.scalars(
            select(Employee).where(Employee.id.in_([k.employee_id for k in kiadasok if k.employee_id]))
        ).all()
    } if kiadasok else {}
    for kiadas in kiadasok:
        fajlok = csatolmanyok.get(kiadas.id) or []
        if not fajlok:
            continue
        allapot, minden_kod, fedezetlen = _fedezettseg(
            [kiadas.project_code_id] if kiadas.project_code_id else [], kodok, kifizetett
        )
        eredmeny.append(
            (
                UtalasraVaroTetel(
                    fedezettseg=allapot,
                    projektkodok=minden_kod,
                    fedezetlen_projektkodok=fedezetlen,
                    kulcs=f"expense:{kiadas.id}",
                    tipus="Kiadás",
                    megnevezes=kiadas.megnevezes,
                    kinek=munkatarsak.get(kiadas.employee_id) if kiadas.employee_id else None,
                    osszeg=float(kiadas.brutto) if kiadas.brutto is not None else (float(kiadas.netto) if kiadas.netto is not None else None),
                    penznem=kiadas.penznem or "HUF",
                    hatarido=kiadas.fizetes_hatarideje,
                    szamla_db=len(fajlok),
                    link=f"/penzugyek/kiadas/{kiadas.id}",
                ),
                [(f"kiadas_{kiadas.id}_{f.id}_{f.filename}", f.storage_key) for f in fajlok],
            )
        )

    kulsos = (
        db.query(PerformanceCertificate)
        .options(
            selectinload(PerformanceCertificate.invoices),
            selectinload(PerformanceCertificate.employee),
            selectinload(PerformanceCertificate.vallalkozas),
            selectinload(PerformanceCertificate.project),
            selectinload(PerformanceCertificate.tetelek).selectinload(PerformanceCertificateTetel.project),
        )
        .filter(PerformanceCertificate.szamla_kifizetve.is_(False))
        .all()
    )
    for tig in kulsos:
        if not tig.invoices:
            continue
        # A fedezet a projektek PROJEKTKÓDJÁN érkezik meg. Egy TIG TÖBB projekt
        # munkáját is igazolhatja (egy ember több forgatást egy számlán küld
        # be) - ilyenkor minden érintett projektkódot nézni kell, és a tétel
        # csak akkor utalható, ha MINDEGYIKRE megjött a pénz. Ez az összevont
        # számlák esete: részben fedezettként látszik, amíg az egyik ügyfél
        # még nem fizetett.
        tig_kodok = [t.project.project_code_id for t in tig.tetelek if t.project is not None]
        if not tig_kodok and tig.project is not None:
            tig_kodok = [tig.project.project_code_id]
        allapot, minden_kod, fedezetlen = _fedezettseg(tig_kodok, kodok, kifizetett)
        eredmeny.append(
            (
                UtalasraVaroTetel(
                    fedezettseg=allapot,
                    projektkodok=minden_kod,
                    fedezetlen_projektkodok=fedezetlen,
                    kulcs=f"kulsos_tig:{tig.id}",
                    tipus="Külsős TIG",
                    megnevezes=tig.megbizas_targya or "Külsős teljesítési igazolás",
                    kinek=(tig.vallalkozas.nev if tig.vallalkozas else None)
                    or (tig.employee.full_name if tig.employee else None),
                    osszeg=float(tig.netto_osszeg) if tig.netto_osszeg is not None else None,
                    penznem="HUF",
                    hatarido=None,
                    szamla_db=len(tig.invoices),
                    link=f"/projektek/{tig.project_id}" if tig.project_id else None,
                ),
                [(f"kulsos_tig_{tig.id}_{sz.id}_{sz.filename}", sz.storage_key) for sz in tig.invoices],
            )
        )

    belsos = (
        db.query(InternalPerformanceCertificate)
        .options(
            selectinload(InternalPerformanceCertificate.invoices),
            selectinload(InternalPerformanceCertificate.employee),
        )
        .filter(InternalPerformanceCertificate.szamla_kifizetve.is_(False))
        .all()
    )
    # A belsős TIG a havi BÉR elszámolása, nem egy megrendelő munkájáé: a
    # fizetés akkor is jár, ha az ügyfél még nem fizetett, tehát belsős TIG
    # SOSEM vár fedezetre - ezeket mindig rögtön utaljuk. Ezért nem nézzük a
    # hónap tételeinek projektkódjait, számlát sem várunk hozzá (a belsős
    # munkatárs nem számlázik, a TIG maga a papír), és az állapotát sem
    # szűrjük: ami nincs kifizetve, az utalandó.
    #
    # Két dolog marad ki: a KIHAGYOTT hónap (akkor nem dolgozott, nincs mit
    # utalni) és az, aminek még nincs összege - azt nem tudnánk mennyivel
    # elutalni, csak üres sorként állna a listán.
    for tig in belsos:
        if tig.allapot == KIHAGYVA or tig.netto_osszeg is None:
            continue
        eredmeny.append(
            (
                UtalasraVaroTetel(
                    fedezettseg=FEDEZETT,
                    kulcs=f"belsos_tig:{tig.id}",
                    tipus="Belsős TIG",
                    # A megnevezés a TIG DÁTUMAIBÓL jön: a 07.20-i fizetési
                    # határidejű a JÚNIUSI elszámolásé (lásd
                    # services/hu_datum.belsos_tig_honapja).
                    megnevezes=f"{ev_honap_szoveg(*_belsos_honap(tig))} havi TIG",
                    kinek=tig.employee.full_name if tig.employee else None,
                    osszeg=float(tig.netto_osszeg) if tig.netto_osszeg is not None else None,
                    penznem="HUF",
                    hatarido=tig.fizetesi_hatarido,
                    szamla_db=len(tig.invoices),
                    link=f"/belsos-tig/{tig.employee_id}/{tig.ev}/{tig.honap}",
                ),
                [(f"belsos_tig_{tig.id}_{sz.id}_{sz.filename}", sz.storage_key) for sz in tig.invoices],
            )
        )

    # A legrégebbi határidő elöl (ami már lejárt, azt kell először utalni), a
    # határidő nélküliek a végén.
    eredmeny.sort(key=lambda p: (p[0].hatarido is None, p[0].hatarido or date.max, p[0].megnevezes))
    return eredmeny


@summary_router.get("/utalasra-varo", response_model=list[UtalasraVaroTetel])
def utalasra_varo(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PENZUGY_PAGE, "view")),
):
    return [tetel for tetel, _ in _utalasra_varo_tetelek(db)]


@summary_router.post("/utalasra-varo/zip")
def utalasra_varo_zip(
    payload: UtalasraVaroKeres,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PENZUGY_PAGE, "view")),
):
    """A KIJELÖLT tételek számlái egyetlen ZIP-ben - ezt viszi az, aki az
    utalásokat indítja. A csomagban egy tartalom.txt is van, hogy utólag
    látszódjon, melyik fájl melyik tételhez (és mekkora összeghez) tartozik."""
    kert = set(payload.kulcsok)
    if not kert:
        raise HTTPException(status_code=400, detail="Nincs kijelölt tétel.")

    valasztott = [(tetel, fajlok) for tetel, fajlok in _utalasra_varo_tetelek(db) if tetel.kulcs in kert]
    if not valasztott:
        raise HTTPException(status_code=404, detail="A kijelölt tételekhez nem található számla.")

    buffer = io.BytesIO()
    hibas: list[str] = []
    leiras: list[str] = []
    osszeg = 0.0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for tetel, fajlok in valasztott:
            osszeg += tetel.osszeg or 0
            if not fajlok:
                # Van olyan tétel, amihez nem is tartozik számla (belsős TIG:
                # a bejelentett munkatárs nem számlázik) - a csomagban ettől
                # még szerepelnie kell, különben az utaló nem látja a listán.
                leiras.append(
                    f"(nincs számla fájl)\t{tetel.tipus}\t{tetel.kinek or '-'}\t{tetel.megnevezes}\t"
                    f"{tetel.osszeg if tetel.osszeg is not None else '-'} {tetel.penznem}\t"
                    f"határidő: {tetel.hatarido or '-'}"
                )
            for nev, kulcs in fajlok:
                try:
                    zf.writestr(nev, document_storage.download_bytes(kulcs))
                except R2NotConfiguredError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                except Exception as exc:  # noqa: BLE001 - egy hiányzó fájl ne buktassa a csomagot
                    hibas.append(f"{nev}\tNEM SIKERÜLT LETÖLTENI: {exc}")
                    continue
                leiras.append(
                    f"{nev}\t{tetel.tipus}\t{tetel.kinek or '-'}\t{tetel.megnevezes}\t"
                    f"{tetel.osszeg if tetel.osszeg is not None else '-'} {tetel.penznem}\t"
                    f"határidő: {tetel.hatarido or '-'}"
                )
        tartalom = [
            f"HYPE OS - utalásra váró számlák ({date.today():%Y-%m-%d})",
            f"{len(valasztott)} tétel, összesen {round(osszeg)} Ft",
            "",
            *leiras,
        ]
        if hibas:
            tartalom += ["", "HIÁNYZÓ FÁJLOK:", *hibas]
        zf.writestr("tartalom.txt", "\n".join(tartalom))

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="utalasra_varo_szamlak_{date.today():%Y%m%d}.zip"'},
    )
