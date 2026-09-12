"""BEÉRKEZŐ SZÁMLÁK - az érkeztető-piszkozatok HTTP-felülete.

A közös folyamat (e-mail ÉS AI Assistant): services/szamla_erkeztetes.py.
A jogosultság a Pénzügyek oldalé: aki a kiadásokat látja/írja, az kezeli a
beérkező számlákat is - kivéve a jóváhagyást, ami "create" jogot kér (éles
pénzügyi rekordot hoz létre).

ADMIN-TEENDŐK A LEVELEZÉS BEKÖTÉSÉHEZ (kód-oldali beállítás nincs több):
1. A szamla@hypestab.hu címre érkező levél jusson el a rendszer Gmail-fiókjába
   (a GMAIL_* hitelesítés fiókja): vagy a fiók ALIAS-a legyen (Google
   Workspace: Felhasználó → Alternatív e-mail címek), vagy a szamla@ postafiók
   ÁLLÍTSON BE TOVÁBBÍTÁST erre a fiókra. DNS/MX átállítás NEM kell, a
   meglévő levelezést nem érinti.
2. Railway env: SZAMLA_BEJOVO_CIM (alapból szamla@hypestab.hu). Automatikus
   lehúzás SZÁNDÉKOSAN nincs (a felhasználó kérése): a leveleket a felület
   "Lehúzás most" gombja hozza be, és csak az OLVASATLANOKAT.
3. A meglévő GMAIL hitelesítésben a gmail.readonly scope már benne van
   (lásd services/google_email.GMAIL_SCOPES) - OAuth tokennél ellenőrizd,
   hogy a token ezzel a scope-pal készült; ha nem, egyszer újra kell kérni."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_page_action
from app.models.auto import Auto
from app.models.bejovo_szamla import (
    ALLAPOT_DUPLIKATUM,
    ALLAPOT_JOVAHAGYVA,
    ALLAPOT_NEM_SZAMLA,
    ALLAPOTOK,
    CEL_TIPUSOK,
    BejovoEmail,
    BejovoSzamla,
)
from app.models.employee import Employee, SystemRole
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.kotelezettseg import KotelezettsegIdoszak
from app.models.performance_certificate import PerformanceCertificate
from app.models.project_code import ProjectCode
from app.services import document_storage, hatter_feladat, szamla_erkeztetes
from app.services.szamla_erkeztetes import ErkeztetesHiba

router = APIRouter(prefix="/bejovo-szamlak", tags=["bejovo-szamlak"])

PAGE = "/penzugyek"
#: A Pénzügyek alap-szerepkör-szűkítését itt sem akarjuk (lásd
#: routes/finance.py) - a page_permissions grant dönt.
_MINDEN_SZEREPKOR = tuple(SystemRole)

EMAIL_LEHUZAS_FELADAT = "szamla-email-lehuzas"


class BejovoListItem(BaseModel):
    id: int
    forras: str
    allapot: str
    fajl_nev: str | None
    url: str | None
    content_type: str | None
    email_felado: str | None
    email_targy: str | None
    email_beerkezes: datetime | None
    created_at: datetime
    dokumentum_tipus: str | None
    szamlaszam: str | None
    kibocsato_nev: str | None
    netto: float | None
    brutto: float | None
    penznem: str
    fizetesi_hatarido: date | None
    irany: str | None
    cel_tipus: str | None
    cel_cimke: str | None = None
    javaslat_indoklas: str | None = None
    jovahagyo_nev: str | None = None
    jovahagyva_at: datetime | None = None
    rogzitett_expense_id: int | None = None
    hiba_uzenet: str | None = None

    model_config = {"from_attributes": True}


class BejovoReszlet(BejovoListItem):
    kinyert: dict | None
    javaslat: dict | None
    felhasznaloi_utasitas: str | None
    kiallitas_datuma: date | None
    teljesites_datuma: date | None
    afa_osszeg: float | None
    kibocsato_adoszam: str | None
    vevo_nev: str | None
    vevo_adoszam: str | None
    email_szoveg: str | None
    cel_project_code_id: int | None
    cel_expense_id: int | None
    cel_certificate_id: int | None
    cel_internal_certificate_id: int | None
    cel_kotelezettseg_idoszak_id: int | None
    cel_auto_id: int | None
    cel_kp_forgalom_id: int | None
    cel_employee_id: int | None
    rogzites_naplo: dict | None
    duplikatum_bejovo_id: int | None
    duplikatum_megjegyzes: str | None
    valtozat_szamla_id: int | None


def _cel_cimke(db: Session, b: BejovoSzamla) -> str | None:
    """Emberi címke a kiválasztott célról - a lista ebből mutatja, hová készül."""
    if b.cel_tipus in ("kiadas_uj", "mukodesi", "auto"):
        reszek = []
        if b.cel_project_code_id:
            pc = db.get(ProjectCode, b.cel_project_code_id)
            if pc:
                reszek.append(pc.projektkod)
        if b.cel_tipus == "auto" and b.cel_auto_id:
            auto = db.get(Auto, b.cel_auto_id)
            if auto:
                reszek.append(auto.rendszam)
        if b.cel_tipus == "mukodesi":
            reszek.append("általános működési költség")
        return "Új kiadás" + (f" – {' / '.join(reszek)}" if reszek else "")
    if b.cel_tipus == "kiadas_csatolas" and b.cel_expense_id:
        exp = db.get(Expense, b.cel_expense_id)
        return f"Számla a #{b.cel_expense_id} kiadáshoz ({exp.megnevezes})" if exp else None
    if b.cel_tipus == "kulsos_tig" and b.cel_certificate_id:
        cert = db.get(PerformanceCertificate, b.cel_certificate_id)
        if cert:
            fel = cert.employee.full_name if cert.employee else (cert.vallalkozas.nev if cert.vallalkozas else "?")
            return f"Külsős TIG #{cert.id} – {fel}"
    if b.cel_tipus == "belsos_tig" and b.cel_internal_certificate_id:
        cert = db.get(InternalPerformanceCertificate, b.cel_internal_certificate_id)
        if cert:
            return f"Belsős TIG {cert.ev}.{cert.honap:02d}"
    if b.cel_tipus == "erezsi" and b.cel_kotelezettseg_idoszak_id:
        idoszak = db.get(KotelezettsegIdoszak, b.cel_kotelezettseg_idoszak_id)
        if idoszak:
            return f"E-Rezsi: {idoszak.kotelezettseg.nev} ({idoszak.esedekesseg})"
    if b.cel_tipus == "kp":
        return "KP-tétel bizonylat"
    if b.cel_tipus == "kimeno":
        return "Kimenő számla (megrendelői folyamat)"
    return None


def _kimenet(db: Session, b: BejovoSzamla, reszletes: bool = False) -> BejovoListItem | BejovoReszlet:
    tipus = BejovoReszlet if reszletes else BejovoListItem
    adat = tipus.model_validate(b)
    adat.cel_cimke = _cel_cimke(db, b)
    adat.javaslat_indoklas = (b.javaslat or {}).get("indoklas")
    adat.jovahagyo_nev = b.jovahagyo.full_name if b.jovahagyo else None
    return adat


def _lekeres(db: Session, bejovo_id: int, zarolva: bool = False) -> BejovoSzamla:
    q = select(BejovoSzamla).where(BejovoSzamla.id == bejovo_id)
    if zarolva:
        q = q.with_for_update()
    b = db.execute(q).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Ez a beérkező számla nem található.")
    return b


@router.get("", response_model=list[BejovoListItem])
def lista(
    allapot: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    q = select(BejovoSzamla).order_by(BejovoSzamla.id.desc()).limit(max(1, min(limit, 500)))
    if allapot:
        if allapot not in ALLAPOTOK:
            raise HTTPException(status_code=400, detail=f"Ismeretlen állapot: {allapot}")
        q = q.where(BejovoSzamla.allapot == allapot)
    return [_kimenet(db, b) for b in db.scalars(q).all()]


@router.get("/email-allapot")
def email_allapot(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A levelezés-bekötés állapota + az utoljára látott levelek."""
    utolso = db.scalars(select(BejovoEmail).order_by(BejovoEmail.id.desc()).limit(20)).all()
    feladat = hatter_feladat.allapot(db, EMAIL_LEHUZAS_FELADAT)
    return {
        "cel_cim": settings.szamla_bejovo_cim,
        "lehuzas_fut": bool(feladat and feladat.running),
        "utolso_lehuzas_log": (feladat.log or "")[-2000:] if feladat else "",
        "utolso_levelek": [
            {
                "felado": e.felado,
                "targy": e.targy,
                "beerkezes": e.beerkezes.isoformat() if e.beerkezes else None,
                "allapot": e.allapot,
                "szamla_db": e.letrehozott_szamla_db,
            }
            for e in utolso
        ],
    }


@router.get("/celok/{tipus}")
def cel_valasztek(
    tipus: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """KERESHETŐ cél-választék a részletes ellenőrzőnek: a megfelelő TIG,
    kiadás, előfizetés-időszak vagy KP-tétel EMBERI címkével (projekt, kód,
    dátum, fél, összeg) - nem belső id-kkal kell dolgozni. A szűrést a
    frontend keresője végzi (KeresosSelect), itt a friss, nyitott tételek
    jönnek."""
    from sqlalchemy import select as sel

    lista: list[dict] = []
    if tipus == "kulsos_tig":
        for cert in db.scalars(
            select(PerformanceCertificate)
            .where(PerformanceCertificate.szamla_kifizetve.is_(False))
            .order_by(PerformanceCertificate.id.desc())
            .limit(400)
        ):
            fel = cert.employee.full_name if cert.employee else (cert.vallalkozas.nev if cert.vallalkozas else "?")
            reszek = [fel]
            if cert.project is not None:
                if cert.project.nev:
                    reszek.append(cert.project.nev)
                if cert.project.forgatas_datuma:
                    reszek.append(cert.project.forgatas_datuma.isoformat())
                pc = db.get(ProjectCode, cert.project.project_code_id) if cert.project.project_code_id else None
                if pc:
                    reszek.append(pc.projektkod)
            elif cert.project_code_id:
                pc = db.get(ProjectCode, cert.project_code_id)
                if pc:
                    reszek.append(pc.projektkod)
            if cert.netto_osszeg is not None:
                reszek.append(f"{float(cert.netto_osszeg):,.0f} Ft".replace(",", " "))
            if cert.invoices:
                reszek.append(f"{len(cert.invoices)} számla már van")
            lista.append({"id": cert.id, "cimke": " – ".join(reszek)})
    elif tipus == "belsos_tig":
        for cert in db.scalars(
            select(InternalPerformanceCertificate)
            .order_by(InternalPerformanceCertificate.ev.desc(), InternalPerformanceCertificate.honap.desc())
            .limit(300)
        ):
            emp = db.get(Employee, cert.employee_id)
            lista.append({"id": cert.id, "cimke": f"{emp.full_name if emp else '?'} – {cert.ev}.{cert.honap:02d}"})
    elif tipus == "kiadas_csatolas":
        for exp in db.scalars(select(Expense).order_by(Expense.id.desc()).limit(400)):
            pc = db.get(ProjectCode, exp.project_code_id) if exp.project_code_id else None
            reszek = [exp.megnevezes]
            if exp.kiadas_leiras:
                reszek.append(exp.kiadas_leiras[:60])
            if pc:
                reszek.append(pc.projektkod)
            if exp.netto is not None:
                reszek.append(f"{float(exp.netto):,.0f} Ft".replace(",", " "))
            if exp.kiadas_datuma:
                reszek.append(exp.kiadas_datuma.isoformat())
            lista.append({"id": exp.id, "cimke": " – ".join(reszek)})
    elif tipus == "erezsi":
        for idoszak in db.scalars(
            sel(KotelezettsegIdoszak).order_by(KotelezettsegIdoszak.esedekesseg.desc()).limit(400)
        ):
            lista.append(
                {
                    "id": idoszak.id,
                    "cimke": f"{idoszak.kotelezettseg.nev}"
                    + (f" ({idoszak.kotelezettseg.csomag})" if idoszak.kotelezettseg.csomag else "")
                    + f" – {idoszak.esedekesseg}"
                    + (" – összeg már beírva" if idoszak.osszeg is not None else ""),
                }
            )
    elif tipus == "kp":
        from app.models.finance import KpForgalom

        for kp in db.scalars(sel(KpForgalom).order_by(KpForgalom.id.desc()).limit(300)):
            lista.append(
                {
                    "id": kp.id,
                    "cimke": f"{kp.forgalom or '?'} – {float(kp.osszeg or 0):,.0f} {kp.penznem}".replace(",", " ")
                    + (f" – {kp.kiadas_datuma}" if kp.kiadas_datuma else ""),
                }
            )
    else:
        raise HTTPException(status_code=400, detail=f"Ehhez a cél-típushoz nincs választék: {tipus}")
    return {"tipus": tipus, "lista": lista}


@router.post("/{bejovo_id}/fajl", response_model=BejovoReszlet)
async def fajl_potlas(
    bejovo_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A LETÖLTÖTT SZÁMLA CSATOLÁSA egy már meglévő (jellemzően csak letöltő-
    linkes levélből nyitott) piszkozathoz - UGYANAZT a tételt folytatja, nem
    kell új asszisztens-beérkezést csinálni. A fájl után a feldolgozás
    (kiolvasás + duplikáció + javaslat) lefut ezen a piszkozaton."""
    b = _lekeres(db, bejovo_id, zarolva=True)
    if b.allapot == ALLAPOT_JOVAHAGYVA:
        raise HTTPException(status_code=409, detail="A már jóváhagyott tételhez nem cserélhető a fájl.")
    adat = await file.read()
    mime = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    from app.services.szamla_erkeztetes import ENGEDETT_MIME, XML_MIME

    if mime not in ENGEDETT_MIME | XML_MIME:
        raise HTTPException(status_code=400, detail=f"Nem támogatott fájltípus: {mime}.")
    if not adat or len(adat) > szamla_erkeztetes.MAX_MERET:
        raise HTTPException(status_code=400, detail="A fájl üres vagy túl nagy (max 20 MB).")
    regi_kulcs = b.storage_key
    b.fajl_nev = (file.filename or "szamla")[:255]
    b.content_type = mime
    b.meret_bajt = len(adat)
    b.fajl_hash = szamla_erkeztetes._hash(adat)
    db.flush()
    import re as _re

    kulcs = f"bejovo-szamla/{b.id}-{_re.sub(r'[^A-Za-z0-9._-]+', '_', b.fajl_nev)[:80]}"
    b.url = document_storage.upload_bytes(adat, kulcs, mime)
    b.storage_key = kulcs
    szamla_erkeztetes.feldolgoz(db, b, adat=adat)
    db.commit()
    if regi_kulcs and regi_kulcs != kulcs:
        try:
            document_storage.delete_object(regi_kulcs)
        except Exception:  # noqa: BLE001
            pass
    db.refresh(b)
    return _kimenet(db, b, reszletes=True)


@router.get("/{bejovo_id}", response_model=BejovoReszlet)
def reszlet(
    bejovo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    return _kimenet(db, _lekeres(db, bejovo_id), reszletes=True)


@router.post("/feltoltes", response_model=BejovoReszlet, status_code=201)
async def feltoltes(
    file: UploadFile = File(...),
    utasitas: str = Form(""),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """Számla feltöltése kézzel vagy az AI Assistantból - a KÖZÖS folyamaton:
    a fájl eltárolódik, kiolvassuk, duplikációt vizsgálunk, besorolási
    javaslattal MENTETT piszkozat készül. Szinkron fut, mert a hívó (a chat)
    a válaszban már a kész ellenőrző-kártyát várja."""
    adat = await file.read()
    try:
        bejovo = szamla_erkeztetes.letrehozas(
            db,
            forras="asszisztens",
            adat=adat,
            fajl_nev=file.filename,
            content_type=file.content_type,
            utasitas=utasitas,
            letrehozo_id=current_user.id,
        )
        szamla_erkeztetes.feldolgoz(db, bejovo, adat=adat)
    except ErkeztetesHiba as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(bejovo)
    return _kimenet(db, bejovo, reszletes=True)


class MezoJavitasIn(BaseModel):
    """A kinyert adatok kézi javítása és/vagy a cél átállítása. Csak a küldött
    mezők változnak; a javított mező forrása "felhasznalo" lesz."""

    szamlaszam: str | None = None
    kibocsato_nev: str | None = None
    kibocsato_adoszam: str | None = None
    netto: float | None = None
    afa_osszeg: float | None = None
    brutto: float | None = None
    penznem: str | None = None
    kiallitas_datuma: date | None = None
    teljesites_datuma: date | None = None
    fizetesi_hatarido: date | None = None
    dokumentum_tipus: str | None = None
    cel_tipus: str | None = None
    cel_project_code_id: int | None = None
    cel_expense_id: int | None = None
    cel_certificate_id: int | None = None
    cel_internal_certificate_id: int | None = None
    cel_kotelezettseg_idoszak_id: int | None = None
    cel_auto_id: int | None = None
    cel_kp_forgalom_id: int | None = None
    cel_employee_id: int | None = None
    felhasznaloi_utasitas: str | None = None


@router.patch("/{bejovo_id}", response_model=BejovoReszlet)
def javitas(
    bejovo_id: int,
    payload: MezoJavitasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    b = _lekeres(db, bejovo_id)
    if b.allapot == ALLAPOT_JOVAHAGYVA:
        raise HTTPException(status_code=409, detail="A már jóváhagyott tétel nem szerkeszthető.")
    valtozasok = payload.model_dump(exclude_unset=True)
    if "cel_tipus" in valtozasok and valtozasok["cel_tipus"] is not None and valtozasok["cel_tipus"] not in CEL_TIPUSOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen cél-típus: {valtozasok['cel_tipus']}")
    # CÉLTÍPUS-VÁLTÁSKOR a régi, az új típushoz nem tartozó rekord-kapcsolat
    # törlődik a piszkozatból (a felhasználó kérése) - különben egy korábbi
    # TIG-hivatkozás némán ott maradna egy "új kiadás" cél mögött.
    if "cel_tipus" in valtozasok and valtozasok["cel_tipus"] != b.cel_tipus:
        TIPUS_MEZOI = {
            "kiadas_uj": {"cel_project_code_id", "cel_employee_id"},
            "mukodesi": {"cel_employee_id"},
            "auto": {"cel_auto_id", "cel_employee_id", "cel_project_code_id"},
            "kiadas_csatolas": {"cel_expense_id"},
            "kulsos_tig": {"cel_certificate_id"},
            "belsos_tig": {"cel_internal_certificate_id"},
            "erezsi": {"cel_kotelezettseg_idoszak_id"},
            "kp": {"cel_kp_forgalom_id"},
        }
        megtartando = TIPUS_MEZOI.get(valtozasok["cel_tipus"] or "", set())
        for mezo in (
            "cel_project_code_id",
            "cel_expense_id",
            "cel_certificate_id",
            "cel_internal_certificate_id",
            "cel_kotelezettseg_idoszak_id",
            "cel_auto_id",
            "cel_kp_forgalom_id",
            "cel_employee_id",
        ):
            if mezo not in megtartando and mezo not in valtozasok:
                setattr(b, mezo, None)
    utasitas_valtozott = "felhasznaloi_utasitas" in valtozasok
    for mezo, ertek in valtozasok.items():
        setattr(b, mezo, ertek)
        # A kézzel javított mező forrása mostantól a felhasználó - az
        # ellenőrző ebből mutatja, mi honnan származik.
        if b.kinyert and mezo not in ("felhasznaloi_utasitas",) and not mezo.startswith("cel_"):
            b.kinyert = {
                **b.kinyert,
                "mezo_forrasok": {**(b.kinyert.get("mezo_forrasok") or {}), mezo: "felhasznalo"},
            }
    if utasitas_valtozott:
        # Az utasítás a besorolás első számú forrása - újrajavaslunk (a már
        # kinyert adatokon, új kiolvasás nélkül).
        szamla_erkeztetes.javasol(db, b)
    db.commit()
    db.refresh(b)
    return _kimenet(db, b, reszletes=True)


class JovahagyasIn(BaseModel):
    cel_tipus: str | None = None
    cel_project_code_id: int | None = None
    cel_expense_id: int | None = None
    cel_certificate_id: int | None = None
    cel_internal_certificate_id: int | None = None
    cel_kotelezettseg_idoszak_id: int | None = None
    cel_auto_id: int | None = None
    cel_kp_forgalom_id: int | None = None
    cel_employee_id: int | None = None
    megnevezes: str | None = None
    kiadas_leiras: str | None = None
    netto: float | None = None
    tipus: str | None = None
    kifizetes_modja: str | None = None
    #: Devizás számlánál KÖTELEZŐ - önkényes árfolyamot nem használunk.
    arfolyam: float | None = None
    #: Több projekt közti felosztás: [{"project_code_id": ..., "netto": ...}] -
    #: az összegeknek pontosan ki kell adniuk a számla nettóját.
    felosztas: list[dict] | None = None


@router.post("/{bejovo_id}/jovahagyas", response_model=BejovoReszlet)
def jovahagyas(
    bejovo_id: int,
    payload: JovahagyasIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """VÉGLEGES RÖGZÍTÉS - sorzárral és ismételt végrehajtás elleni védelemmel:
    két párhuzamos jóváhagyás (vagy dupla kattintás) közül csak az első rögzít,
    a második a már megtörtént eredményt kapja. Az éles összesítők eddig a
    pillanatig változatlanok voltak."""
    b = _lekeres(db, bejovo_id, zarolva=True)
    try:
        szamla_erkeztetes.jovahagy(db, b, current_user, payload.model_dump(exclude_unset=True))
    except ErkeztetesHiba as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(b)
    return _kimenet(db, b, reszletes=True)


class AllapotIn(BaseModel):
    megjegyzes: str | None = None


@router.post("/{bejovo_id}/duplikatum", response_model=BejovoReszlet)
def duplikatumnak_jelol(
    bejovo_id: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    b = _lekeres(db, bejovo_id, zarolva=True)
    if b.allapot == ALLAPOT_JOVAHAGYVA:
        raise HTTPException(status_code=409, detail="Jóváhagyott tétel már nem jelölhető duplikátumnak.")
    b.allapot = ALLAPOT_DUPLIKATUM
    b.duplikatum_megjegyzes = payload.megjegyzes or b.duplikatum_megjegyzes
    db.commit()
    db.refresh(b)
    return _kimenet(db, b, reszletes=True)


@router.post("/{bejovo_id}/nem-szamla", response_model=BejovoReszlet)
def nem_szamlanak_jelol(
    bejovo_id: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    b = _lekeres(db, bejovo_id, zarolva=True)
    if b.allapot == ALLAPOT_JOVAHAGYVA:
        raise HTTPException(status_code=409, detail="Jóváhagyott tétel már nem utasítható el.")
    b.allapot = ALLAPOT_NEM_SZAMLA
    b.duplikatum_megjegyzes = payload.megjegyzes or b.duplikatum_megjegyzes
    db.commit()
    db.refresh(b)
    return _kimenet(db, b, reszletes=True)


@router.post("/{bejovo_id}/ujrafeldolgozas", response_model=BejovoReszlet)
def ujrafeldolgozas(
    bejovo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Új kiolvasás + javaslat - hibás vagy elakadt tételhez (megszakítás utáni
    folytatás). A jóváhagyott tételhez nem nyúl."""
    b = _lekeres(db, bejovo_id, zarolva=True)
    if b.allapot == ALLAPOT_JOVAHAGYVA:
        raise HTTPException(status_code=409, detail="Jóváhagyott tétel nem dolgozható fel újra.")
    b.hiba_uzenet = None
    szamla_erkeztetes.feldolgoz(db, b)
    db.commit()
    db.refresh(b)
    return _kimenet(db, b, reszletes=True)


@router.delete("/{bejovo_id}", response_model=None)
def torles(
    bejovo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Egy beérkező számla-piszkozat VÉGLEGES törlése - bármelyik állapotban
    (a felhasználó kérése). A tárolt fájl is törlődik az R2-ről.

    A jóváhagyáskor MÁR LÉTREJÖTT rekordokat (kiadás, TIG-számla sor,
    csatolmány) a törlés NEM bántja: azok saját másolatban őrzik a fájlt, és
    a maguk felületén kezelhetők - itt csak az érkeztető-piszkozat tűnik el.
    Az eredeti e-mail a postafiókban marad; a bejovo_emailek napló is marad,
    tehát a törölt levél egy újabb lehúzással nem jön vissza magától."""
    b = _lekeres(db, bejovo_id, zarolva=True)
    kulcs = b.storage_key
    # A hozzá kapcsolt formátum-változat (pl. XML) kapcsolata magától oldódik
    # (SET NULL) - a változat-sor megmarad, önállóan törölhető.
    db.delete(b)
    db.commit()
    if kulcs:
        try:
            document_storage.delete_object(kulcs)
        except Exception:  # noqa: BLE001 - az árva objektum nem éri meg az 500-at
            pass
    return None


class ResetIn(BaseModel):
    #: Kifejezett megerősítés - e nélkül a hívás nem fut le.
    megerosites: str


@router.post("/reset")
def tiszta_ujrainditas(
    payload: ResetIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """TISZTA ÚJRAINDÍTÁS: az eddigi érkeztetési beérkezések kitakarítása
    (lásd services/szamla_reset.py) - CSAK ADMIN, kifejezett megerősítéssel.

    Mentés + tételes visszaállítási jegyzék készül; a jóváhagyott tételek
    mellékhatásai bizonyítható eredet alapján vonódnak vissza (a nem
    bizonyítható rendezendő kivételként jelölődik); a kizárási napló megmarad,
    így a kitakarított levelek nem jönnek vissza a következő lehúzáskor. Az
    eredeti postafiókhoz nem nyúlunk."""
    from app.models.employee import SystemRole, van_szerepkore

    if not van_szerepkore(current_user, SystemRole.ADMIN):
        raise HTTPException(status_code=403, detail="A tiszta újraindítást csak admin futtathatja.")
    if payload.megerosites.strip().upper() != "TISZTA INDULAS":
        raise HTTPException(
            status_code=400,
            detail='A megerősítéshez írd be pontosan: "TISZTA INDULAS".',
        )
    from app.services import szamla_reset

    return szamla_reset.teljes_reset(db, current_user)


class LehuzasIn(BaseModel):
    #: Régi levelek visszamenőleges feldolgozásához - választható kezdődátum.
    kezdo_datum: date | None = None
    limit: int = 50
    #: Előnézet: semmit nem hoz létre, csak megmutatja, mi történne.
    elonezet: bool = False


@router.post("/email-lehuzas")
def email_lehuzas(
    payload: LehuzasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A célcímre érkezett levelek lehúzása MOST (kézi indítás). Idempotens:
    a már látott üzenetek kimaradnak (lásd services/szamla_email_lehuzas.py)."""
    try:
        return szamla_email_lehuzas_futtatasa(db, payload)
    except RuntimeError as exc:
        # Hiányzó Gmail-hitelesítés: beszédes hibával, nem 500-zal.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def szamla_email_lehuzas_futtatasa(db, payload: LehuzasIn) -> dict:
    from app.services import szamla_email_lehuzas as lehuzo

    return lehuzo.lehuzas(
        db,
        kezdo_datum=payload.kezdo_datum,
        limit=max(1, min(payload.limit, 200)),
        csak_elonezet=payload.elonezet,
    )
