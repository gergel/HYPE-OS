"""Eszközkivitel - publikus (kódos) és kezelő végpontok.

Lásd models/eszkoz_kivitel.py: a forgatásra kimenő ember egy 6 jegyű kóddal,
bejelentkezés nélkül írja be, mit vitt ki és mit hozott vissza; a kezelő
oldalon (bejelentkezve) látszik az összes kivitel és a HIÁNY (ami nem jött
vissza). A kódot egyelőre a kezelő oldalon lehet generálni - a
diszpó-kiküldésbe szándékosan nincs bekötve (a felhasználó kérése: előbb
önállóan tesztelődjön)."""

from __future__ import annotations

import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment
from app.models.eszkoz_kivitel import EszkozKivitel, EszkozKivitelTetel
from app.models.project import Project

PAGE = "/eszkozkivitelek"

#: A mindig élő teszt-kód (a felhasználó kérése) - a hozzá tartozó kivitel
#: projekt nélküli, és a kezelő oldalon TESZT-ként látszik.
ADMIN_KOD = "admin"

#: A forgatás vége után ennyi napig él még a kód.
ERVENYESSEG_NAP = 7

public_router = APIRouter(prefix="/public/eszkozkivitel", tags=["eszkozkivitel-public"])
admin_router = APIRouter(prefix="/eszkozkivitelek", tags=["eszkozkivitel-admin"])


def ervenyes_eddig(kivitel: EszkozKivitel) -> date | None:
    """Meddig él a kód. None = nincs időkorlát (teszt, vagy dátum nélküli
    projekt - utóbbiról nem tudjuk, mikor lesz/volt, inkább maradjon nyitva)."""
    if kivitel.teszt or kivitel.project is None:
        return None
    veg = kivitel.project.forgatas_datuma_vege or kivitel.project.forgatas_datuma
    if veg is None:
        return None
    return veg + timedelta(days=ERVENYESSEG_NAP)

def kivitel_ervenyes(kivitel: EszkozKivitel) -> bool:
    hatar = ervenyes_eddig(kivitel)
    return hatar is None or date.today() <= hatar


def _kivitel_a_kodhoz(db: Session, kod: str) -> EszkozKivitel:
    """A kódhoz tartozó ÉLŐ kivitel - az admin kód mindig él (és ha még nincs
    hozzá teszt-kivitel, most jön létre)."""
    tisztitott = (kod or "").strip().lower()
    if tisztitott == ADMIN_KOD:
        kivitel = db.scalar(select(EszkozKivitel).where(EszkozKivitel.kod == ADMIN_KOD))
        if kivitel is None:
            kivitel = EszkozKivitel(kod=ADMIN_KOD, teszt=True)
            db.add(kivitel)
            db.commit()
            db.refresh(kivitel)
        return kivitel
    kivitel = db.scalar(select(EszkozKivitel).where(EszkozKivitel.kod == tisztitott))
    if kivitel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen kód.")
    if not kivitel_ervenyes(kivitel):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ez a kód már lejárt (a forgatás vége után 7 napig él).",
        )
    return kivitel


# ── Publikus válasz-sémák ────────────────────────────────────────────────────


class EszkozInfo(BaseModel):
    id: int
    nev: str
    kategoria: str | None = None


class AjanlottTetel(EszkozInfo):
    """A forgatásra KIÍRT technika (Assignment) - csak súgó a kivitelhez."""

    db: int = 1


class KivitelTetelInfo(EszkozInfo):
    kivitt_db: int
    visszahozott_db: int


class BelepesValasz(BaseModel):
    projekt_nev: str | None
    forgatas_datuma: date | None
    forgatas_vege: date | None
    ervenyes_eddig: date | None
    teszt: bool
    #: "kivitel" | "vissza" | "lezart" - lásd models/eszkoz_kivitel.py.
    allapot: str
    ajanlott: list[AjanlottTetel]
    tetelek: list[KivitelTetelInfo]
    #: A teljes eszközkészlet a keresőhöz - kategória szerint csoportosítva
    #: jeleníti meg a felület.
    eszkozok: list[EszkozInfo]


class BelepesKeres(BaseModel):
    kod: str


class TetelKeres(BaseModel):
    equipment_id: int
    kivitt_db: int | None = None
    visszahozott_db: int | None = None
    #: PÓT-KIVITEL a visszahozatal fázisban: ennyivel NŐ a kivitt darabszám.
    #: Szándékosan csak növelés (nem beállítás): a korábban beírt kivitelt a
    #: visszahozatal fázisban már nem lehet se látni, se csökkenteni - ez
    #: zárja ki a "visszaírom kevesebbre, amit kivittem" csalást.
    kivitt_hozzaadas: int | None = None


def _tetelek_valasz(db: Session, kivitel: EszkozKivitel, publikus: bool = False) -> list[KivitelTetelInfo]:
    """A tételek. `publikus=True` esetén a kivitel-fázis LEZÁRÁSA után a
    kivitt darabszámok kinullázva mennek ki - a hiány csak a kezelő oldalon
    derülhet ki, és a hálózati válaszból se lehessen kiolvasni, mit kellene
    "visszahozottnak" írni (a felhasználó kérése)."""
    sorok = db.scalars(
        select(EszkozKivitelTetel)
        .where(EszkozKivitelTetel.kivitel_id == kivitel.id)
        .options(selectinload(EszkozKivitelTetel.equipment))
        .order_by(EszkozKivitelTetel.id)
    ).all()
    rejtett_kivitt = publikus and kivitel.allapot != "kivitel"
    return [
        KivitelTetelInfo(
            id=t.equipment_id,
            nev=t.equipment.nev if t.equipment else f"#{t.equipment_id}",
            kategoria=t.equipment.kategoria if t.equipment else None,
            kivitt_db=0 if rejtett_kivitt else t.kivitt_db,
            visszahozott_db=t.visszahozott_db,
        )
        for t in sorok
    ]


def _belepes_valasz(db: Session, kivitel: EszkozKivitel) -> BelepesValasz:
    ajanlott: list[AjanlottTetel] = []
    if kivitel.project_id is not None:
        foglalasok = db.scalars(
            select(Assignment)
            .where(Assignment.project_id == kivitel.project_id)
            .options(selectinload(Assignment.equipment))
        ).all()
        for f in foglalasok:
            if f.equipment is None:
                continue
            ajanlott.append(
                AjanlottTetel(
                    id=f.equipment_id,
                    nev=f.equipment.nev,
                    kategoria=f.equipment.kategoria,
                    db=f.qty or 1,
                )
            )
    eszkozok = [
        EszkozInfo(id=e.id, nev=e.nev, kategoria=e.kategoria)
        for e in db.scalars(select(Equipment).order_by(Equipment.kategoria, Equipment.nev)).all()
    ]
    project = kivitel.project
    return BelepesValasz(
        projekt_nev=project.nev if project else ("TESZT KIVITEL" if kivitel.teszt else None),
        forgatas_datuma=project.forgatas_datuma if project else None,
        forgatas_vege=(project.forgatas_datuma_vege or project.forgatas_datuma) if project else None,
        ervenyes_eddig=ervenyes_eddig(kivitel),
        teszt=kivitel.teszt,
        allapot=kivitel.allapot,
        ajanlott=ajanlott,
        tetelek=_tetelek_valasz(db, kivitel, publikus=True),
        eszkozok=eszkozok,
    )


@public_router.post("/belepes", response_model=BelepesValasz)
def belepes(payload: BelepesKeres, db: Session = Depends(get_db)):
    """Belépés kóddal - vissza a forgatás adatai, a kiírt technika (súgó), a
    már beírt tételek és a keresőhöz a teljes eszközlista.

    Az admin (teszt) kivitel LEZÁRT állapotban belépéskor tisztán újraindul
    - így akárhányszor végig lehet próbálni a teljes folyamatot."""
    kivitel = _kivitel_a_kodhoz(db, payload.kod)
    if kivitel.teszt and kivitel.allapot == "lezart":
        db.query(EszkozKivitelTetel).filter(EszkozKivitelTetel.kivitel_id == kivitel.id).delete()
        kivitel.allapot = "kivitel"
        kivitel.megjegyzes = None
        db.commit()
    return _belepes_valasz(db, kivitel)


@public_router.put("/{kod}/tetel", response_model=list[KivitelTetelInfo])
def tetel_mentes(kod: str, payload: TetelKeres, db: Session = Depends(get_db)):
    """Egy eszköz darabszámainak beírása (upsert) - FÁZISHOZ kötve.

    - "kivitel" fázisban csak a kivitt darab írható (kivitt_db);
    - "vissza" fázisban a visszahozott darab írható (visszahozott_db), és
      pót-kivitel vihető fel NÖVELÉSKÉNT (kivitt_hozzaadas) - a korábbi
      kivitel nem látható és nem csökkenthető (ne lehessen csalni);
    - "lezart" állapotban semmi.

    Ha a kivitel fázisban mindkét szám nullára csökken, a sor törlődik -
    így a véletlen kattintás visszavonható."""
    kivitel = _kivitel_a_kodhoz(db, kod)
    if kivitel.allapot == "lezart":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ez a kivitel már le van zárva.")
    if kivitel.allapot == "kivitel" and (payload.visszahozott_db is not None or payload.kivitt_hozzaadas is not None):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A visszahozatal csak a kivitel lezárása után írható.",
        )
    if kivitel.allapot == "vissza" and payload.kivitt_db is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A kivitel már lezárult - pót-kivitel csak hozzáadásként vihető fel.",
        )
    eszkoz = db.get(Equipment, payload.equipment_id)
    if eszkoz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen eszköz.")
    tetel = db.scalar(
        select(EszkozKivitelTetel).where(
            EszkozKivitelTetel.kivitel_id == kivitel.id,
            EszkozKivitelTetel.equipment_id == payload.equipment_id,
        )
    )
    if tetel is None:
        tetel = EszkozKivitelTetel(kivitel_id=kivitel.id, equipment_id=payload.equipment_id)
        db.add(tetel)
    if payload.kivitt_db is not None:
        tetel.kivitt_db = max(0, payload.kivitt_db)
    if payload.kivitt_hozzaadas is not None:
        # Csak pozitív irányban - lásd a TetelKeres mező-kommentjét.
        tetel.kivitt_db = (tetel.kivitt_db or 0) + max(0, payload.kivitt_hozzaadas)
    if payload.visszahozott_db is not None:
        tetel.visszahozott_db = max(0, payload.visszahozott_db)
    if tetel.kivitt_db == 0 and tetel.visszahozott_db == 0:
        if tetel.id is not None:
            db.delete(tetel)
        else:
            db.expunge(tetel)
    db.commit()
    return _tetelek_valasz(db, kivitel, publikus=True)


class LezarasKeres(BaseModel):
    #: "kivitel" (kivitel vége -> jöhet a visszahozatal) vagy "vissza"
    #: (minden lezárva).
    mit: str
    #: A visszahozatal lezárásakor megadható észrevétel - kihagyható.
    megjegyzes: str | None = None


@public_router.post("/{kod}/lezaras", response_model=BelepesValasz)
def lezaras(kod: str, payload: LezarasKeres, db: Session = Depends(get_db)):
    """Fázis-lezárás: a kivitel vége után jön a visszahozatal, a
    visszahozatal vége után minden lezárul (opcionális észrevétellel)."""
    kivitel = _kivitel_a_kodhoz(db, kod)
    if payload.mit == "kivitel":
        if kivitel.allapot != "kivitel":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A kivitel már le van zárva.")
        kivitel.allapot = "vissza"
    elif payload.mit == "vissza":
        if kivitel.allapot != "vissza":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A visszahozatal csak a kivitel lezárása után zárható le.",
            )
        kivitel.allapot = "lezart"
        if payload.megjegyzes and payload.megjegyzes.strip():
            kivitel.megjegyzes = payload.megjegyzes.strip()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ismeretlen lezárás.")
    db.commit()
    return _belepes_valasz(db, kivitel)


# ── Kezelő végpontok (bejelentkezve, saját oldal-joggal) ─────────────────────


class KivitelAdminSor(BaseModel):
    id: int
    kod: str
    teszt: bool
    project_id: int | None
    projekt_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    ervenyes_eddig: date | None
    ervenyes: bool
    allapot: str
    #: A visszahozatal lezárásakor megadott észrevétel (ha volt).
    megjegyzes: str | None
    tetelek: list[KivitelTetelInfo]
    #: Hány tételből hoztak vissza kevesebbet, mint amennyi kiment.
    hianyos_tetelek: int


class GeneralasKeres(BaseModel):
    project_id: int


def _admin_sor(db: Session, kivitel: EszkozKivitel) -> KivitelAdminSor:
    tetelek = _tetelek_valasz(db, kivitel)
    project = kivitel.project
    return KivitelAdminSor(
        id=kivitel.id,
        kod=kivitel.kod,
        teszt=kivitel.teszt,
        project_id=kivitel.project_id,
        projekt_nev=project.nev if project else None,
        projektkod=project.projektkod_szoveg if project else None,
        forgatas_datuma=project.forgatas_datuma if project else None,
        ervenyes_eddig=ervenyes_eddig(kivitel),
        ervenyes=kivitel_ervenyes(kivitel),
        allapot=kivitel.allapot,
        megjegyzes=kivitel.megjegyzes,
        tetelek=tetelek,
        hianyos_tetelek=sum(1 for t in tetelek if t.visszahozott_db < t.kivitt_db),
    )


@admin_router.get("", response_model=list[KivitelAdminSor])
def list_kivitelek(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    kivitelek = db.scalars(
        select(EszkozKivitel)
        .options(selectinload(EszkozKivitel.project))
        .order_by(EszkozKivitel.id.desc())
    ).all()
    return [_admin_sor(db, k) for k in kivitelek]


def _uj_kod(db: Session) -> str:
    """Egyedi, 6 számjegyű kód - ütközésnél újrapróbálkozik."""
    for _ in range(50):
        kod = str(secrets.randbelow(900000) + 100000)
        if db.scalar(select(EszkozKivitel.id).where(EszkozKivitel.kod == kod)) is None:
            return kod
    raise HTTPException(status_code=500, detail="Nem sikerült egyedi kódot generálni.")


@admin_router.post("/generalas", response_model=KivitelAdminSor)
def kod_generalas(
    payload: GeneralasKeres,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Kód generálása egy forgatáshoz - ha már van, azt adja vissza (egy
    forgatás = egy kivitel, a stáb közösen tölti)."""
    project = db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")
    meglevo = db.scalar(select(EszkozKivitel).where(EszkozKivitel.project_id == project.id))
    if meglevo is not None:
        return _admin_sor(db, meglevo)
    kivitel = EszkozKivitel(project_id=project.id, kod=_uj_kod(db))
    db.add(kivitel)
    db.commit()
    db.refresh(kivitel)
    return _admin_sor(db, kivitel)


class AllapotKeres(BaseModel):
    allapot: str


@admin_router.post(
    "/{kivitel_id}/allapot",
    response_model=KivitelAdminSor,
    dependencies=[Depends(require_page_action(PAGE, "edit"))],
)
def set_allapot(kivitel_id: int, payload: AllapotKeres, db: Session = Depends(get_db)):
    """A kivitel fázisának átállítása a KEZELŐ oldalról (a felhasználó
    kérése): kivitel lezárása, visszahozatal lezárása, vagy egy lezárt
    kivitel újranyitása - az irodából, a kód nélkül is."""
    if payload.allapot not in ("kivitel", "vissza", "lezart"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ismeretlen állapot.")
    kivitel = db.get(EszkozKivitel, kivitel_id)
    if kivitel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen kivitel.")
    kivitel.allapot = payload.allapot
    db.commit()
    db.refresh(kivitel)
    return _admin_sor(db, kivitel)


@admin_router.delete(
    "/{kivitel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_page_action(PAGE, "delete"))],
)
def delete_kivitel(kivitel_id: int, db: Session = Depends(get_db)):
    kivitel = db.get(EszkozKivitel, kivitel_id)
    if kivitel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen kivitel.")
    db.delete(kivitel)
    db.commit()
