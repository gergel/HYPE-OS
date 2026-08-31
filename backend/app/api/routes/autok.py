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

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import Role, get_current_user, lathatjak_az_oldalt, require_page_action
from app.models.auto import Auto, AutoTeendo, AutoTeendoKomment
from app.api.routes import kotelezettsegek
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.project_code import ProjectCode
from app.services import elszamolas
from app.services import kotelezettseg as szolg
from app.services import notifications

router = APIRouter(prefix="/autok", tags=["autok"])

PAGE = "/autok"

#: A durva admin/operator szerepkör-kapu itt nem érvényes: akinek admin a
#: Beállításokban jogot adott erre az oldalra, az a szerepkörétől
#: függetlenül dolgozhat rajta (ugyanaz az elv, mint az Utómunkánál -
#: lásd routes/postproduction.py _MINDEN_SZEREPKOR). A page_permissions
#: védelem változatlanul él.
_MINDEN_SZEREPKOR = tuple(Role)

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
    #: Melyik PROJEKTKÓD költsége (a felhasználó kérése: a tankolás a
    #: projektnél is látsszon). UGYANAZ az egy Expense-sor - a Pénzügyben
    #: egyszer szerepel, az autó és a projektkód csak két nézete.
    project_code_id: int | None = None
    projektkod: str | None = None


class AutoHataridoRead(BaseModel):
    """Egy határidő az autó lapján - a mögötte lévő kötelezettségből."""

    id: int
    nev: str
    tipus: str
    kovetkezo_esedekesseg: date | None = None
    napok_hatra: int | None = None
    allapot: str


class AutoTeendoKommentRead(BaseModel):
    """Hozzászólás egy autó-teendő alatt - ugyanaz a chat-minta, mint a HYPE
    TO-DO kommenteknél (lásd models/auto.AutoTeendoKomment)."""

    id: int
    auto_teendo_id: int
    employee_id: int
    employee_name: str
    body: str
    created_at: datetime


class AutoTeendoRead(BaseModel):
    """Egy teendő az autó lapján - pipálható lista járművenként (lásd
    models/auto.AutoTeendo)."""

    id: int
    auto_id: int
    szoveg: str
    kesz: bool = False
    hatarido: date | None = None
    felelos_id: int | None = None
    felelos_nev: str | None = None
    kommentek: list[AutoTeendoKommentRead] = []


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
    teendok: list[AutoTeendoRead] = []
    #: A rá könyvelt kiadások NETTÓ összege forintban (a devizás sorokat nem
    #: számoljuk át - nincs árfolyam-forrás a rendszerben, egy kitalált
    #: átváltás pedig hamis összeget adna).
    koltseg_osszesen: float = 0
    #: A legsürgetőbb határidő állapota: lejart | hamarosan | rendben | nincs.
    hatarido_allapot: str = "nincs"


def _kiadas_kimenet(e: Expense, dokumentumok: dict[int, int] | None = None) -> AutoKiadasRead:
    # Az `osszeg` a BRUTTÓ: a táblázat külön oszlopban mutatja a nettót és a
    # bruttót, mert az autónál mindkettő érdekes (a nettó számol, a bruttó
    # megy ki a számláról). Az összesítés viszont nettóban megy - lásd
    # `_kimenet` és services/elszamolas.py.
    osszeg = elszamolas.brutto_osszeg(e) if (e.brutto is not None or e.netto is not None) else None
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
        project_code_id=e.project_code_id,
        projektkod=e.project_code.projektkod if e.project_code is not None else None,
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
    # NETTÓBAN, ahogy mindenütt máshol is az elszámolásban (lásd
    # services/elszamolas.py) - az ÁFA átfolyó tétel, nem az autó költsége.
    #
    # MINDEN sor beleszámít: a tárolt összeg mindig forint, a devizás tételt a
    # felvezetéskor váltjuk át (lásd services/penznem.py). Korábban itt egy
    # `penznem == "HUF"` szűrő állt, ami a nem forintos sorokat NÉMÁN kihagyta -
    # vagyis egy euróban fizetett szerviz úgy tűnt el az autó költségéből,
    # mintha nem is lett volna.
    osszesen = float(sum(elszamolas.osszeg(e) for e in auto.kiadasok))

    if any(h.allapot == "lejart" for h in hataridok):
        allapot = "lejart"
    elif any(h.allapot == "hamarosan" for h in hataridok):
        allapot = "hamarosan"
    elif hataridok:
        allapot = "rendben"
    else:
        allapot = "nincs"

    # A bizonylat-darabszámokat EGYSZER kérdezzük le az összes kiadásra -
    # korábban ez a lekérdezés kiadásonként újra lefutott (N+1).
    dokumentumok = _kiadas_dokumentumok(db, [x.id for x in kiadasok])

    # A nyitott teendők elöl (a lejártabb határidő előrébb), a készek hátul.
    teendok = sorted(
        auto.teendok,
        key=lambda t: (t.kesz, t.hatarido is None, t.hatarido or ma, t.id),
    )

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
        kiadasok=[_kiadas_kimenet(e, dokumentumok) for e in kiadasok],
        teendok=[_teendo_kimenet(t) for t in teendok],
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
                selectinload(Auto.teendok).selectinload(AutoTeendo.felelos),
                selectinload(Auto.teendok)
                .selectinload(AutoTeendo.kommentek)
                .selectinload(AutoTeendoKomment.employee),
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
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
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
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
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
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
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
    #: Ha a költés egy PROJEKT miatt merült fel (pl. tankolás egy forgatáshoz),
    #: itt köthető a projektkódhoz - a kiadás beleszámít a kód költségeibe,
    #: de mivel ugyanaz az EGY sor, a Pénzügyben nem duplázódik.
    project_code_id: int | None = None


@router.post("/{auto_id}/kiadasok", response_model=AutoKiadasRead, status_code=201)
def create_auto_kiadas(
    auto_id: int,
    payload: AutoKiadasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
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

    if payload.project_code_id is not None and db.get(ProjectCode, payload.project_code_id) is None:
        raise HTTPException(status_code=404, detail="A megadott projektkód nem található.")

    datum = payload.datum or date.today()
    kiadas = Expense(
        megnevezes=f"{auto.rendszam} – {payload.megnevezes.strip()}",
        auto_id=auto.id,
        project_code_id=payload.project_code_id,
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
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
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


# --- Teendők autónként -------------------------------------------------------
# Pipálható lista minden járműhöz ("vinni műszakira", "izzót cserélni") - a
# felhasználó kérése. Lásd models/auto.AutoTeendo; a lista az AutoRead
# `teendok` mezőjében jön a felületre.


class AutoTeendoIn(BaseModel):
    szoveg: str
    hatarido: date | None = None
    felelos_id: int | None = None


class AutoTeendoUpdate(BaseModel):
    szoveg: str | None = None
    kesz: bool | None = None
    hatarido: date | None = None
    felelos_id: int | None = None
    #: Melyik mezők változnak ténylegesen - enélkül egy "csak pipálás" PATCH a
    #: None-ra maradt határidőt/felelőst is kiürítené.
    model_config = {"extra": "forbid"}


def _teendo_felelos_ellenorzese(db: Session, felelos_id: int | None) -> None:
    """Teendő felelősének csak az jelölhető, akinek admin hozzáférést adott az
    Autók oldalhoz (a felhasználó kérése) - ugyanaz a szabály, mint a HYPE
    TO-DO Felelős-választójánál (lásd core/security.lathatjak_az_oldalt). A
    felület is ezt a szűrt listát kínálja fel (lásd AutoTeendok.tsx), ez itt
    a szerveroldali biztosíték."""
    if felelos_id is None:
        return
    if felelos_id not in lathatjak_az_oldalt(db, PAGE):
        raise HTTPException(
            status_code=400,
            detail="Teendő felelősének csak olyan munkatárs jelölhető, akinek van hozzáférése az Autók oldalhoz.",
        )


def _komment_kimenet(c: AutoTeendoKomment) -> AutoTeendoKommentRead:
    return AutoTeendoKommentRead(
        id=c.id,
        auto_teendo_id=c.auto_teendo_id,
        employee_id=c.employee_id,
        employee_name=c.employee.full_name,
        body=c.body,
        created_at=c.created_at,
    )


def _teendo_kimenet(t: AutoTeendo) -> AutoTeendoRead:
    return AutoTeendoRead(
        id=t.id,
        auto_id=t.auto_id,
        szoveg=t.szoveg,
        kesz=t.kesz,
        hatarido=t.hatarido,
        felelos_id=t.felelos_id,
        felelos_nev=t.felelos.full_name if t.felelos else None,
        kommentek=[_komment_kimenet(c) for c in t.kommentek],
    )


@router.post("/{auto_id}/teendok", response_model=AutoTeendoRead, status_code=201)
def create_auto_teendo(
    auto_id: int,
    payload: AutoTeendoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    if db.get(Auto, auto_id) is None:
        raise HTTPException(status_code=404, detail="Az autó nem található.")
    szoveg = payload.szoveg.strip()
    if not szoveg:
        raise HTTPException(status_code=400, detail="A teendő szövege nem lehet üres.")
    _teendo_felelos_ellenorzese(db, payload.felelos_id)
    teendo = AutoTeendo(auto_id=auto_id, szoveg=szoveg, hatarido=payload.hatarido, felelos_id=payload.felelos_id)
    db.add(teendo)
    db.commit()
    db.refresh(teendo)
    return _teendo_kimenet(teendo)


@router.patch("/{auto_id}/teendok/{teendo_id}", response_model=AutoTeendoRead)
def update_auto_teendo(
    auto_id: int,
    teendo_id: int,
    payload: AutoTeendoUpdate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    teendo = db.get(AutoTeendo, teendo_id)
    if teendo is None or teendo.auto_id != auto_id:
        raise HTTPException(status_code=404, detail="A teendő nem található ennél az autónál.")
    valtozasok = payload.model_dump(exclude_unset=True)
    if "felelos_id" in valtozasok:
        _teendo_felelos_ellenorzese(db, valtozasok["felelos_id"])
    if "szoveg" in valtozasok:
        szoveg = (valtozasok["szoveg"] or "").strip()
        if not szoveg:
            raise HTTPException(status_code=400, detail="A teendő szövege nem lehet üres.")
        valtozasok["szoveg"] = szoveg
    for mezo, ertek in valtozasok.items():
        setattr(teendo, mezo, ertek)
    db.commit()
    db.refresh(teendo)
    return _teendo_kimenet(teendo)


@router.delete("/{auto_id}/teendok/{teendo_id}", status_code=204)
def delete_auto_teendo(
    auto_id: int,
    teendo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    teendo = db.get(AutoTeendo, teendo_id)
    if teendo is None or teendo.auto_id != auto_id:
        raise HTTPException(status_code=404, detail="A teendő nem található ennél az autónál.")
    db.delete(teendo)
    db.commit()


# --- Hozzászólások a teendőkhöz ---------------------------------------------
# Ugyanaz a chat-szerű minta, mint a HYPE TO-DO és a FLÓRA kommentjeinél (lásd
# routes/hype_todo.py) - kommentelni az oldal MEGTEKINTÉSI jogával lehet, mert
# a beszélgetés nem a rekord szerkesztése.


class AutoTeendoKommentCreate(BaseModel):
    body: str


def _teendo_betoltese(db: Session, auto_id: int, teendo_id: int) -> AutoTeendo:
    teendo = db.get(AutoTeendo, teendo_id)
    if teendo is None or teendo.auto_id != auto_id:
        raise HTTPException(status_code=404, detail="A teendő nem található ennél az autónál.")
    return teendo


@router.get("/{auto_id}/teendok/{teendo_id}/kommentek", response_model=list[AutoTeendoKommentRead])
def get_teendo_kommentek(
    auto_id: int,
    teendo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    teendo = _teendo_betoltese(db, auto_id, teendo_id)
    return [_komment_kimenet(c) for c in teendo.kommentek]


@router.post("/{auto_id}/teendok/{teendo_id}/kommentek", response_model=AutoTeendoKommentRead, status_code=201)
def post_teendo_komment(
    auto_id: int,
    teendo_id: int,
    payload: AutoTeendoKommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    teendo = _teendo_betoltese(db, auto_id, teendo_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="A hozzászólás nem lehet üres.")

    komment = AutoTeendoKomment(auto_teendo_id=teendo.id, employee_id=current_user.id, body=body)
    db.add(komment)
    db.commit()
    db.refresh(komment)

    # @Név említésnél a megemlített, egyébként a teendő felelőse kap
    # értesítést - ugyanaz a minta, mint a HYPE TO-DO kommenteknél.
    cim = f"{teendo.auto.rendszam}: {teendo.szoveg}"
    mar_ertesitett: set[int] = set()
    for employee_id in notifications.extract_mentioned_employee_ids(body, db):
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="mention",
            message=f"{current_user.full_name} megemlített egy hozzászólásban: {cim}",
            link="/autok",
            actor_id=current_user.id,
        )
        mar_ertesitett.add(employee_id)
    if teendo.felelos_id and teendo.felelos_id not in mar_ertesitett:
        notifications.create_notification(
            db,
            employee_id=teendo.felelos_id,
            kind="comment",
            message=f"{current_user.full_name} kommentelt: {cim}",
            link="/autok",
            actor_id=current_user.id,
        )
    db.commit()

    return _komment_kimenet(komment)
