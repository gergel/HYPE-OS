"""Céges autók: a papírjaik lejárata és a rájuk költött pénz.

A jármű maga sovány rekord - a tartalom két, már meglévő rendszerből jön
(lásd models/auto.py):

- a HATÁRIDŐK (forgalmi, biztosítás) kötelezettségek, tehát ugyanaz a
  lejárat-figyelés, értesítés és feladat vonatkozik rájuk, mint bármelyik
  előfizetésre (routes/kotelezettsegek.py);
- a KÖLTSÉGEK sima kiadások (`expenses.auto_id`), tehát az itt felvitt tankolás
  és szerviz ugyanazzal a rekorddal jelenik meg a Pénzügy összesítő kiadásai
  közt - nincs másolat, amit szinkronban kellene tartani.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.auto import Auto
from app.api.routes import kotelezettsegek
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.models.finance import Expense
from app.services import kotelezettseg as szolg

router = APIRouter(prefix="/autok", tags=["autok"])

PAGE = "/autok"

#: Mire költünk egy autóra. Szabad szöveg is beírható - ez csak a gyors
#: választás a felületen, nem korlátozás.
KOLTSEG_FAJTAK = ("Tankolás", "Szerviz", "Alkatrész", "Gumi", "Autópálya-matrica", "Parkolás", "Mosás", "Egyéb")

#: A költéshez feltöltött dokumentum (számla, blokk) entity_type-ja. Külön név
#: a sima "expense"-től, pedig ugyanaz a tábla: a jogosultsága így az AUTÓK
#: oldaláé, nem a Pénzügyé - egy tankolási blokk feltöltéséhez ne kelljen
#: hozzáférés a cég teljes pénzügyéhez (lásd services/attachments.py).
KIADAS_ENTITAS = "autoKiadas"


class AutoKiadasRead(BaseModel):
    id: int
    megnevezes: str
    datum: date | None = None
    #: Nettó és bruttó: a bruttó a nettóból és az áfa-jelölésből áll elő
    #: (lásd routes/kotelezettsegek.brutto), de a kiadás-soron mindkettő ott
    #: van, mert a Pénzügy a bruttóval számol.
    netto: float | None = None
    plusz_afa: bool = False
    osszeg: float | None = None
    penznem: str = "HUF"
    fizetesi_mod: str | None = None
    megjegyzes: str | None = None
    #: Ki lett-e már fizetve (a Pénzügy oldal ezt is kezeli).
    kesz: bool = False
    #: Hány dokumentum (számla, blokk) van feltöltve hozzá.
    dokumentum_db: int = 0


class AutoHataridoRead(BaseModel):
    """Egy határidő az autó lapján - a mögötte lévő kötelezettségből."""

    id: int
    nev: str
    tipus: str
    kovetkezo_esedekesseg: date | None = None
    napok_hatra: int | None = None
    allapot: str


class AutoRead(BaseModel):
    id: int
    rendszam: str
    megnevezes: str | None = None
    tipus: str | None = None
    evjarat: int | None = None
    km_ora: int | None = None
    felelos_id: int | None = None
    felelos_nev: str | None = None
    aktiv: bool = True
    megjegyzes: str | None = None

    hataridok: list[AutoHataridoRead] = []
    kiadasok: list[AutoKiadasRead] = []
    #: A rá könyvelt kiadások összege forintban (a devizás sorokat nem
    #: számoljuk át - nincs árfolyam-forrás a rendszerben, egy kitalált
    #: átváltás pedig hamis összeget adna).
    koltseg_osszesen: float = 0
    #: A legsürgetőbb határidő állapota: lejart | hamarosan | rendben | nincs.
    hatarido_allapot: str = "nincs"


def _kiadas_kimenet(e: Expense, dokumentumok: dict[int, int] | None = None) -> AutoKiadasRead:
    # A kiadásnál a bruttó a fizetett összeg; ha csak nettó van, azt adjuk.
    osszeg = e.brutto if e.brutto is not None else e.netto
    return AutoKiadasRead(
        id=e.id,
        megnevezes=e.megnevezes,
        datum=e.kiadas_datuma or e.fizetes_datuma,
        netto=float(e.netto) if e.netto is not None else None,
        # A "+ÁFA" jelölést a kiadás szöveges mezője hordozza (a Notionból
        # örökölt alak) - a felületnek viszont igen/nem kell.
        plusz_afa=(e.plusz_afa or "").strip().lower() in ("igen", "true", "+afa", "+áfa"),
        osszeg=float(osszeg) if osszeg is not None else None,
        penznem=e.penznem or "HUF",
        fizetesi_mod=e.kifizetes_modja,
        megjegyzes=e.megjegyzes,
        kesz=bool(e.kesz),
        dokumentum_db=(dokumentumok or {}).get(e.id, 0),
    )


def _kiadas_dokumentumok(db: Session, kiadas_idk: list[int]) -> dict[int, int]:
    if not kiadas_idk:
        return {}
    sorok = db.scalars(
        select(DocumentAttachment).where(
            DocumentAttachment.entity_type == KIADAS_ENTITAS,
            DocumentAttachment.entity_id.in_(kiadas_idk),
        )
    ).all()
    darab: dict[int, int] = {}
    for sor in sorok:
        darab[sor.entity_id] = darab.get(sor.entity_id, 0) + 1
    return darab


def _kimenet(db: Session, auto: Auto, ma: date) -> AutoRead:
    hataridok = [
        AutoHataridoRead(
            id=k.id,
            nev=k.nev,
            tipus=k.tipus,
            kovetkezo_esedekesseg=szolg.kovetkezo_esedekesseg(k, ma),
            napok_hatra=szolg.hatralevo_napok(k, ma),
            allapot=szolg.allapot(k, ma),
        )
        for k in auto.kotelezettsegek
    ]
    hataridok.sort(key=lambda h: (h.kovetkezo_esedekesseg is None, h.kovetkezo_esedekesseg or ma))

    kiadasok = sorted(
        auto.kiadasok,
        key=lambda e: (e.kiadas_datuma or e.fizetes_datuma or date.min),
        reverse=True,
    )
    osszesen = sum(
        float(e.brutto if e.brutto is not None else (e.netto or 0))
        for e in auto.kiadasok
        if (e.penznem or "HUF") == "HUF"
    )

    if any(h.allapot == "lejart" for h in hataridok):
        allapot = "lejart"
    elif any(h.allapot == "hamarosan" for h in hataridok):
        allapot = "hamarosan"
    elif hataridok:
        allapot = "rendben"
    else:
        allapot = "nincs"

    return AutoRead(
        id=auto.id,
        rendszam=auto.rendszam,
        megnevezes=auto.megnevezes,
        tipus=auto.tipus,
        evjarat=auto.evjarat,
        km_ora=auto.km_ora,
        felelos_id=auto.felelos_id,
        felelos_nev=auto.felelos.full_name if auto.felelos else None,
        aktiv=auto.aktiv,
        megjegyzes=auto.megjegyzes,
        hataridok=hataridok,
        kiadasok=[_kiadas_kimenet(e, _kiadas_dokumentumok(db, [x.id for x in kiadasok])) for e in kiadasok],
        koltseg_osszesen=osszesen,
        hatarido_allapot=allapot,
    )


def _betolt(db: Session) -> list[Auto]:
    return list(
        db.scalars(
            select(Auto)
            .options(
                selectinload(Auto.kotelezettsegek),
                selectinload(Auto.kiadasok),
                selectinload(Auto.felelos),
            )
            .order_by(Auto.rendszam)
        ).all()
    )


@router.get("", response_model=list[AutoRead])
def list_autok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az autók a papírjaik állapotával és az eddigi költségükkel.

    Mint a kötelezettségeknél: a lekérés hozza magával a lejáratok
    "utolérését" is, mert ütemező nincs a rendszerben."""
    szolg.ensure_mindent(db)
    ma = date.today()
    return [_kimenet(db, a, ma) for a in _betolt(db)]


@router.get("/{auto_id}", response_model=AutoRead)
def get_auto(auto_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    auto = db.get(Auto, auto_id)
    if auto is None:
        raise HTTPException(status_code=404, detail="Az autó nem található.")
    szolg.ensure_mindent(db)
    return _kimenet(db, auto, date.today())


class AutoIn(BaseModel):
    rendszam: str
    megnevezes: str | None = None
    tipus: str | None = None
    evjarat: int | None = None
    km_ora: int | None = None
    felelos_id: int | None = None
    aktiv: bool = True
    megjegyzes: str | None = None


def _rendszam_szabad(db: Session, rendszam: str, kiveve_id: int | None = None) -> None:
    letezo = db.scalar(select(Auto).where(Auto.rendszam == rendszam))
    if letezo is not None and letezo.id != kiveve_id:
        raise HTTPException(status_code=409, detail=f"Ezzel a rendszámmal már van autó felvéve: {rendszam}")


@router.post("", response_model=AutoRead, status_code=201)
def create_auto(
    payload: AutoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    rendszam = payload.rendszam.strip().upper()
    if not rendszam:
        raise HTTPException(status_code=400, detail="A rendszám kötelező.")
    _rendszam_szabad(db, rendszam)
    auto = Auto(**{**payload.model_dump(), "rendszam": rendszam})
    db.add(auto)
    db.commit()
    db.refresh(auto)
    return _kimenet(db, auto, date.today())


@router.put("/{auto_id}", response_model=AutoRead)
def update_auto(
    auto_id: int,
    payload: AutoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    auto = db.get(Auto, auto_id)
    if auto is None:
        raise HTTPException(status_code=404, detail="Az autó nem található.")
    rendszam = payload.rendszam.strip().upper()
    if not rendszam:
        raise HTTPException(status_code=400, detail="A rendszám kötelező.")
    _rendszam_szabad(db, rendszam, auto_id)
    for mezo, ertek in payload.model_dump().items():
        setattr(auto, mezo, ertek)
    auto.rendszam = rendszam
    db.commit()
    db.refresh(auto)
    return _kimenet(db, auto, date.today())


@router.delete("/{auto_id}", status_code=204)
def delete_auto(
    auto_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Az autó törlése.

    A rá könyvelt KIADÁSOK megmaradnak, csak elveszítik az autó-hivatkozásukat:
    megtörtént pénzmozgásokat nem törlünk egy törzsadat kedvéért. A határidői
    viszont vele mennek - azoknak nélküle nincs értelmük."""
    auto = db.get(Auto, auto_id)
    if auto is None:
        raise HTTPException(status_code=404, detail="Az autó nem található.")
    for kiadas in auto.kiadasok:
        kiadas.auto_id = None
    db.delete(auto)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Költések
# ─────────────────────────────────────────────────────────────────────────────


class AutoKiadasIn(BaseModel):
    #: Mire ment ("Tankolás", "Szerviz - fékbetét"…).
    megnevezes: str
    datum: date | None = None
    #: NETTÓ összeg. A bruttót ebből és az áfa-jelölésből számoljuk, hogy a
    #: kettő sose mondhasson ellent egymásnak.
    osszeg: float
    plusz_afa: bool = False
    penznem: str = "HUF"
    #: "Átutalás" | "Készpénz" | "Bankkártya" - ugyanaz a szókészlet, mint a
    #: Pénzügy kiadásainál, hogy a kimutatás egyben lássa őket.
    fizetesi_mod: str | None = None
    megjegyzes: str | None = None
    #: Ki van-e már fizetve. Alapból igen: ami az autónál felmerül (tankolás,
    #: parkolás), azt jellemzően a helyszínen kifizetik.
    kifizetve: bool = True


@router.post("/{auto_id}/kiadasok", response_model=AutoKiadasRead, status_code=201)
def create_auto_kiadas(
    auto_id: int,
    payload: AutoKiadasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Költés felvitele az autóra.

    A rekord SIMA KIADÁS (Expense), csak az `auto_id` köti a járműhöz - ezért
    jelenik meg magától a Pénzügy összesítő kiadásai közt is
    (`hozzaadas_a_kiadasokhoz`), és ezért nem tud a két hely szétcsúszni."""
    auto = db.get(Auto, auto_id)
    if auto is None:
        raise HTTPException(status_code=404, detail="Az autó nem található.")
    if not payload.megnevezes.strip():
        raise HTTPException(status_code=400, detail="Add meg, mire ment a költés.")

    datum = payload.datum or date.today()
    kiadas = Expense(
        megnevezes=f"{auto.rendszam} – {payload.megnevezes.strip()}",
        auto_id=auto.id,
        tipus="extra",
        netto=payload.osszeg,
        brutto=kotelezettsegek.brutto(payload.osszeg, payload.plusz_afa),
        plusz_afa="Igen" if payload.plusz_afa else None,
        penznem=payload.penznem or "HUF",
        kifizetes_modja=payload.fizetesi_mod,
        kiadas_datuma=datum,
        fizetes_datuma=datum if payload.kifizetve else None,
        kesz=payload.kifizetve,
        hozzaadas_a_kiadasokhoz=True,
        megjegyzes=payload.megjegyzes,
    )
    db.add(kiadas)
    db.commit()
    db.refresh(kiadas)
    return _kiadas_kimenet(kiadas)


@router.delete("/kiadasok/{kiadas_id}", status_code=204)
def delete_auto_kiadas(
    kiadas_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Az autóhoz felvitt költés törlése.

    Csak az autós kiadásokat engedjük innen törölni: a Pénzügy más soraihoz
    ennek a végpontnak semmi köze, és egy elgépelt azonosítóval nem eshet ki
    egy projekt kiadása."""
    kiadas = db.get(Expense, kiadas_id)
    if kiadas is None or kiadas.auto_id is None:
        raise HTTPException(status_code=404, detail="Ez a kiadás nem található az autóknál.")
    db.delete(kiadas)
    db.commit()
