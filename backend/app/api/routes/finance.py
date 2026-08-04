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
from app.models.internal_performance_certificate import InternalPerformanceCertificateInvoice
from app.models.performance_certificate import PerformanceCertificateInvoice
from app.models.project_code import ProjectCode
from app.services import document_storage
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

expenses_router = build_crud_router(
    model=Expense,
    create_schema=ExpenseCreate,
    update_schema=ExpenseUpdate,
    read_schema=ExpenseRead,
    prefix="/expenses",
    tags=["finance"],
    page="/penzugyek",
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
    ytd_bevetel: float
    ytd_kiadas: float
    ytd_profit: float
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
# sorok esnek ki. A projektkód-szintű Expense.brutto összeg (ProjectCode.
# osszes_koltseg) ettől függetlenül MINDIG az adott projekt teljes,
# valós költségét mutatja - ez a gate csak a globális Pénzügy nézetet szűri.
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

    ytd_bevetel = (
        db.scalar(
            select(func.coalesce(func.sum(Revenue.brutto), 0)).where(
                Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= year_start
            )
        )
        or 0
    )
    ytd_kiadas = (
        db.scalar(
            select(func.coalesce(func.sum(Expense.brutto), 0)).where(
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
            func.coalesce(func.sum(Revenue.brutto), 0).label("total"),
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
            func.coalesce(func.sum(Expense.brutto), 0).label("total"),
        )
        .where(Expense.fizetes_datuma.is_not(None), Expense.fizetes_datuma >= min_date, _EXPENSE_COUNTS_TOWARD_TOTALS)
        .group_by("y", "m")
    ).all():
        expense_by_month[(int(row.y), int(row.m))] = float(row.total)

    ytd_kiadas_fizetesi_mod_szerint = [
        PaymentMethodBreakdown(kifizetes_modja=row.kifizetes_modja, osszeg=float(row.total))
        for row in db.execute(
            select(Expense.kifizetes_modja, func.coalesce(func.sum(Expense.brutto), 0).label("total"))
            .where(Expense.fizetes_datuma.is_not(None), Expense.fizetes_datuma >= year_start, _EXPENSE_COUNTS_TOWARD_TOTALS)
            .group_by(Expense.kifizetes_modja)
            .order_by(func.sum(Expense.brutto).desc())
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
        osszeg = sum(r.brutto or 0 for r in rows)
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
        honap_jel = f"{cert.ev}-{cert.honap:02d}" if cert else "ismeretlen"
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
