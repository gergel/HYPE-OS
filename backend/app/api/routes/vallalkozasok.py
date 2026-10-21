"""Vállalkozások (számlázó cégek) kezelése.

Két dolgot ad a felületnek:

1. a cégek listáját és adatlapját - kikkel dolgozunk cégen keresztül, kik
   tartoznak hozzájuk, és van-e velük élő keretszerződés;
2. a tagság szerkesztését - ez a "kik tartoznak egy adott céghez" opció.

Fontos, hogy a tagság csak JAVASLAT: azt, hogy egy konkrét forgatáson kinek a
munkáját ki számlázza, a projekt-beosztás dönti el (lásd
models/project_szamlazo.py). Ugyanaz az ember "ma innen számláz, holnap saját
névről, utána egy harmadik helyről" - ezért nem lehet egy cég-mutatót az
emberre akasztani.

Ha egy cégnek van élő keretszerződése, a tőle jövő emberektől NEM kérünk eseti
szerződést azokon a projekteken, ahol ő a számlázó fél (lásd
routes/subcontractor_contracts.py)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import Contract, ContractType, keretszerzodes_ervenyes, megkotott_keretszerzodes
from app.models.employee import Employee
from app.models.performance_certificate import PerformanceCertificate
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.vallalkozas import Vallalkozas, VallalkozasTag

router = APIRouter(prefix="/vallalkozasok", tags=["vallalkozasok"])

# A cégek a Pénzügyek alatt élnek, a Keretszerződések fül mellett.
PAGE = "/penzugyek"

# Az ember felőli (adatlapos) cég-kezelés a Csapat oldalhoz tartozik: ott
# vezetjük fel, kinek melyik cége van.
CSAPAT_PAGE = "/csapat"


class TagInfo(BaseModel):
    employee_id: int
    full_name: str
    tipus: str | None = None
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


class VallalkozasRead(BaseModel):
    id: int
    nev: str
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None
    megbizas_targya: str | None = None
    plusz_afa: bool | None = None
    megjegyzes: str | None = None
    aktiv: bool = True
    tagok: list[TagInfo] = []
    #: Van-e MA élő keretszerződése (lásd models/contract.py
    #: keretszerzodes_ervenyes) - ettől függ, kell-e eseti szerződés a tőle
    #: jövő emberektől.
    van_ervenyes_keretszerzodes: bool = False
    keretszerzodes_id: int | None = None


#: Amit egy számlázó cégről KÖTELEZŐ tudni, mert mind rákerül a papírra.
#:
#: A cég nevére szóló szerződés és TIG ezekből a mezőkből áll össze (lásd
#: routes/subcontractor_contracts.py és performance_certificates.py) - ha
#: bármelyik hiányzik, a kiküldött dokumentumon üres hely marad, amit utólag
#: csak új papírral lehet javítani. Ezért a felvitelnél kérjük be mindet, nem
#: a kiküldés pillanatában.
KOTELEZO_CEG_MEZOK: dict[str, str] = {
    "nev": "Cég neve",
    "kepviselo": "Képviselő",
    "szekhely": "Székhely",
    "adoszam": "Adószám",
    "nyilvantartasi_szam": "Nyilvántartási szám",
    "megbizas_targya": "Megbízás tárgya",
}


def _hianyzo_kotelezo(ertekek: dict[str, object]) -> list[str]:
    """Mely kötelező mezők hiányoznak (üres string is hiánynak számít)?"""
    return [
        cimke
        for mezo, cimke in KOTELEZO_CEG_MEZOK.items()
        if mezo in ertekek and not str(ertekek.get(mezo) or "").strip()
    ]


class VallalkozasIn(BaseModel):
    nev: str
    szekhely: str
    adoszam: str
    kepviselo: str
    nyilvantartasi_szam: str
    megbizas_targya: str
    email: str | None = None
    plusz_afa: bool | None = None
    megjegyzes: str | None = None
    aktiv: bool = True


class VallalkozasPatch(BaseModel):
    nev: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None
    megbizas_targya: str | None = None
    plusz_afa: bool | None = None
    megjegyzes: str | None = None
    aktiv: bool | None = None


class TagIn(BaseModel):
    employee_id: int
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


def _keretszerzodesei(db: Session, vallalkozas_ids: set[int]) -> dict[int, list[Contract]]:
    if not vallalkozas_ids:
        return {}
    rows = (
        db.query(Contract)
        .options(selectinload(Contract.idoszakok))
        .filter(
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.vallalkozas_id.in_(vallalkozas_ids),
            Contract.project_id.is_(None),
        )
        .all()
    )
    eredmeny: dict[int, list[Contract]] = {}
    for c in rows:
        if megkotott_keretszerzodes(c):
            eredmeny.setdefault(c.vallalkozas_id, []).append(c)
    return eredmeny


def _olvasas(v: Vallalkozas, keretek: list[Contract]) -> VallalkozasRead:
    ervenyes = next((c for c in keretek if keretszerzodes_ervenyes(c)), None)
    return VallalkozasRead(
        id=v.id,
        nev=v.nev,
        szekhely=v.szekhely,
        adoszam=v.adoszam,
        kepviselo=v.kepviselo,
        nyilvantartasi_szam=v.nyilvantartasi_szam,
        email=v.email,
        megbizas_targya=v.megbizas_targya,
        plusz_afa=v.plusz_afa,
        megjegyzes=v.megjegyzes,
        aktiv=v.aktiv,
        tagok=[
            TagInfo(
                employee_id=t.employee_id,
                full_name=t.employee.full_name if t.employee else f"#{t.employee_id}",
                tipus=t.employee.tipus.value if t.employee and t.employee.tipus else None,
                kezdet=t.kezdet,
                veg=t.veg,
                megjegyzes=t.megjegyzes,
            )
            for t in v.tagok
        ],
        van_ervenyes_keretszerzodes=ervenyes is not None,
        keretszerzodes_id=(ervenyes or (keretek[0] if keretek else None)).id if keretek else None,
    )


def _get_or_404(db: Session, vallalkozas_id: int) -> Vallalkozas:
    v = db.get(Vallalkozas, vallalkozas_id)
    if v is None:
        raise HTTPException(status_code=404, detail="A vállalkozás nem található.")
    return v


@router.get("", response_model=list[VallalkozasRead])
def list_vallalkozasok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    rows = (
        db.query(Vallalkozas)
        .options(selectinload(Vallalkozas.tagok).selectinload(VallalkozasTag.employee))
        .order_by(Vallalkozas.aktiv.desc(), Vallalkozas.nev)
        .all()
    )
    keretek = _keretszerzodesei(db, {v.id for v in rows})
    return [_olvasas(v, keretek.get(v.id, [])) for v in rows]

# ─────────────────────────────────────────────────────────────────────────────
# Ember felől: melyik cégekhez tartozik, mettől meddig
#
# Ugyanaz a VallalkozasTag tábla, csak a MÁSIK irányból nézve - a munkatárs
# adatlapján itt lehet felvezetni a cégeit. Az időszak azért kell, mert egy
# ember hónapról hónapra más cégről számlázhat: a belsős havi TIG ebből tudja,
# melyik céget ajánlja fel az adott hónapra (lásd
# routes/internal_performance_certificates.py).
# ─────────────────────────────────────────────────────────────────────────────


class EmberCegInfo(BaseModel):
    #: A TAGSÁG azonosítója (nem a cégé) - ezzel szerkeszthető/törölhető a sor.
    id: int
    vallalkozas_id: int
    nev: str
    aktiv: bool = True
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


class EmberCegIn(BaseModel):
    vallalkozas_id: int
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


class EmberCegModosit(BaseModel):
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


def _ember_cegei(db: Session, employee_id: int) -> list[EmberCegInfo]:
    """A munkatárs cégei, a legfrissebb időszakkal elöl."""
    tagsagok = (
        db.query(VallalkozasTag)
        .options(selectinload(VallalkozasTag.vallalkozas))
        .filter(VallalkozasTag.employee_id == employee_id)
        .all()
    )
    sorok = [
        EmberCegInfo(
            id=t.id,
            vallalkozas_id=t.vallalkozas_id,
            nev=t.vallalkozas.nev if t.vallalkozas else f"#{t.vallalkozas_id}",
            aktiv=t.vallalkozas.aktiv if t.vallalkozas else True,
            kezdet=t.kezdet,
            veg=t.veg,
            megjegyzes=t.megjegyzes,
        )
        for t in tagsagok
    ]
    # A nyitott végű (ma is élő) időszak elöl, utána a kezdet szerint csökkenőben.
    sorok.sort(key=lambda x: (x.veg is not None, -(x.kezdet.toordinal() if x.kezdet else 0)))
    return sorok


def _tagsag_or_404(db: Session, tagsag_id: int) -> VallalkozasTag:
    tag = db.get(VallalkozasTag, tagsag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Ez a cég-tagság nem található.")
    return tag


@router.get("/ember/{employee_id}", response_model=list[EmberCegInfo])
def ember_cegei(employee_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található.")
    return _ember_cegei(db, employee_id)


@router.post("/ember/{employee_id}", response_model=list[EmberCegInfo])
def ember_ceg_felvetel(
    employee_id: int,
    payload: EmberCegIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(CSAPAT_PAGE, "edit")),
):
    """Cég felvezetése a munkatárshoz, időszakkal.

    Egy emberhez több cég is tartozhat - de ugyanaz a cég csak egyszer: ha
    időben visszatér ugyanahhoz a céghez, a meglévő sor időszakát kell
    bővíteni, különben nem lenne eldönthető, melyik sor érvényes."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található.")
    if db.get(Vallalkozas, payload.vallalkozas_id) is None:
        raise HTTPException(status_code=404, detail="A cég nem található.")
    if payload.kezdet and payload.veg and payload.veg < payload.kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet korábbi, mint a kezdete.")
    letezo = (
        db.query(VallalkozasTag)
        .filter(
            VallalkozasTag.employee_id == employee_id,
            VallalkozasTag.vallalkozas_id == payload.vallalkozas_id,
        )
        .first()
    )
    if letezo is not None:
        raise HTTPException(status_code=400, detail="Ez a cég már fel van véve ehhez a munkatárshoz.")
    db.add(VallalkozasTag(employee_id=employee_id, **payload.model_dump()))
    db.commit()
    return _ember_cegei(db, employee_id)


@router.patch("/tagsagok/{tagsag_id}", response_model=list[EmberCegInfo])
def ember_ceg_modositas(
    tagsag_id: int,
    payload: EmberCegModosit,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(CSAPAT_PAGE, "edit")),
):
    """Az időszak (és a megjegyzés) módosítása."""
    tag = _tagsag_or_404(db, tagsag_id)
    if payload.kezdet and payload.veg and payload.veg < payload.kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet korábbi, mint a kezdete.")
    tag.kezdet = payload.kezdet
    tag.veg = payload.veg
    tag.megjegyzes = payload.megjegyzes
    db.commit()
    return _ember_cegei(db, tag.employee_id)


@router.delete("/tagsagok/{tagsag_id}", response_model=list[EmberCegInfo])
def ember_ceg_torles(
    tagsag_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(CSAPAT_PAGE, "delete")),
):
    """A cég levétele a munkatársról.

    A már elkészült papírokat nem érinti: azok a saját másolatukban őrzik a
    cég adatait."""
    tag = _tagsag_or_404(db, tagsag_id)
    employee_id = tag.employee_id
    db.delete(tag)
    db.commit()
    return _ember_cegei(db, employee_id)


@router.get("/{vallalkozas_id}", response_model=VallalkozasRead)
def get_vallalkozas(vallalkozas_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    v = _get_or_404(db, vallalkozas_id)
    return _olvasas(v, _keretszerzodesei(db, {v.id}).get(v.id, []))


@router.post("", response_model=VallalkozasRead, status_code=201)
def create_vallalkozas(
    payload: VallalkozasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    hianyzik = _hianyzo_kotelezo(payload.model_dump())
    if hianyzik:
        raise HTTPException(
            status_code=400,
            detail=f"Ezek a mezők kötelezőek: {', '.join(hianyzik)}. Mind rákerül a cég nevére szóló papírra.",
        )
    v = Vallalkozas(**payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return _olvasas(v, [])


@router.patch("/{vallalkozas_id}", response_model=VallalkozasRead)
def update_vallalkozas(
    vallalkozas_id: int,
    payload: VallalkozasPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    v = _get_or_404(db, vallalkozas_id)
    valtozas = payload.model_dump(exclude_unset=True)
    # A kötelező mezőt szerkesztéskor sem lehet KIÜRÍTENI - különben a
    # felvitelnél bekért adat egy javítással eltűnhetne, és a következő papír
    # már hiányosan menne ki. Amit nem küld a kérés, azt nem bántjuk.
    hianyzik = _hianyzo_kotelezo(valtozas)
    if hianyzik:
        raise HTTPException(
            status_code=400,
            detail=f"Ezek a mezők nem maradhatnak üresen: {', '.join(hianyzik)}.",
        )
    for mezo, ertek in valtozas.items():
        setattr(v, mezo, ertek)
    db.commit()
    db.refresh(v)
    return _olvasas(v, _keretszerzodesei(db, {v.id}).get(v.id, []))


@router.delete("/{vallalkozas_id}", status_code=204)
def delete_vallalkozas(
    vallalkozas_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Csak akkor törölhető, ha semmilyen papír nem hivatkozik rá.

    Egy cég törlése különben szerződéseket és TIG-eket tenne "gazdátlanná",
    illetve némán visszaállítaná az érintett projekteken az emberekre a
    számlázást - ilyet nem szabad mellékhatásként. Ha már nem dolgozunk vele,
    az `aktiv` kapcsolót kell kikapcsolni: a régi papírok megmaradnak, de új
    beosztásnál nem ajánljuk fel."""
    v = _get_or_404(db, vallalkozas_id)
    akadalyok = []
    if db.query(Contract.id).filter(Contract.vallalkozas_id == v.id).first():
        akadalyok.append("szerződés")
    if db.query(PerformanceCertificate.id).filter(PerformanceCertificate.vallalkozas_id == v.id).first():
        akadalyok.append("TIG")
    if db.query(ProjectSzamlazo.id).filter(ProjectSzamlazo.szamlazo_vallalkozas_id == v.id).first():
        akadalyok.append("projekt-beosztás")
    if akadalyok:
        raise HTTPException(
            status_code=400,
            detail=(
                "A cég nem törölhető, mert hivatkozik rá: "
                + ", ".join(akadalyok)
                + ". Kapcsold inkább inaktívra."
            ),
        )
    db.delete(v)
    db.commit()


@router.post("/{vallalkozas_id}/tagok", response_model=VallalkozasRead)
def add_tag(
    vallalkozas_id: int,
    payload: TagIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Ember hozzáadása a céghez. Egy ember TÖBB céghez is tartozhat: nem
    ritka, hogy hol az egyik, hol a másik nevében számláz."""
    v = _get_or_404(db, vallalkozas_id)
    if db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található.")
    if any(t.employee_id == payload.employee_id for t in v.tagok):
        raise HTTPException(status_code=400, detail="Ez az ember már tagja ennek a cégnek.")
    v.tagok.append(VallalkozasTag(**payload.model_dump()))
    db.commit()
    db.refresh(v)
    return _olvasas(v, _keretszerzodesei(db, {v.id}).get(v.id, []))


@router.delete("/{vallalkozas_id}/tagok/{employee_id}", response_model=VallalkozasRead)
def remove_tag(
    vallalkozas_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Ember levétele a céglistáról.

    A már elkészült papírokat (és a projekteken beállított számlázó felet) NEM
    érinti: ez csak a javaslati lista, nem a történet."""
    v = _get_or_404(db, vallalkozas_id)
    tag = next((t for t in v.tagok if t.employee_id == employee_id), None)
    if tag is None:
        raise HTTPException(status_code=404, detail="Ez az ember nem tagja ennek a cégnek.")
    v.tagok.remove(tag)
    db.commit()
    db.refresh(v)
    return _olvasas(v, _keretszerzodesei(db, {v.id}).get(v.id, []))
