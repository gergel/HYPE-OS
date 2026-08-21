"""A HYPE 2026 diszpótábla HTTP-felülete: munkalapok, rács, cella-szerkesztés.

A rács TÖMÖREN megy ki: a cellák nem objektumok, hanem `[sor, oszlop, érték,
szín]` négyesek. A külsős munkalap 34 ezer cellája objektumokként több
megabájt volna minden oldalbetöltésnél - és pont ez az a felület, amit egész
nap nyitva tartanak.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.diszpo_tabla import (
    SZINEK,
    DiszpoCella,
    DiszpoMunkalap,
    DiszpoOszlop,
    DiszpoSor,
)
from app.models.employee import Employee
from app.services import munkanap_szamlalo

router = APIRouter(prefix="/diszpo-tabla", tags=["diszpo-tabla"])

PAGE = "/diszpo-tabla"


class MunkalapFej(BaseModel):
    id: int
    nev: str
    sorrend: int
    sor_szam: int
    oszlop_szam: int
    fejlec_sorok: int

    model_config = {"from_attributes": True}


class OszlopOut(BaseModel):
    idx: int
    cimke: str | None = None
    csoport: str | None = None
    employee_id: int | None = None
    employee_nev: str | None = None


class SorOut(BaseModel):
    idx: int
    datum: date | None = None
    nap: str | None = None
    diszposzam: int | None = None
    elvalaszto: bool = False


class MunkalapOut(MunkalapFej):
    oszlopok: list[OszlopOut]
    sorok: list[SorOut]
    #: [sor_idx, oszlop_idx, érték, szín] - lásd a modul leírását.
    cellak: list[tuple[int, int, str | None, str | None]]


@router.get("", response_model=list[MunkalapFej])
def list_munkalapok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A fülek - a rács tartalma nélkül."""
    return [
        MunkalapFej.model_validate(m)
        for m in db.scalars(select(DiszpoMunkalap).order_by(DiszpoMunkalap.sorrend, DiszpoMunkalap.id)).all()
    ]


def _munkalap_vagy_404(db: Session, munkalap_id: int) -> DiszpoMunkalap:
    m = db.get(DiszpoMunkalap, munkalap_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Ez a munkalap nem található.")
    return m


@router.get("/{munkalap_id}", response_model=MunkalapOut)
def get_munkalap(munkalap_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    m = _munkalap_vagy_404(db, munkalap_id)
    oszlopok = db.scalars(
        select(DiszpoOszlop)
        .options(selectinload(DiszpoOszlop.employee))
        .where(DiszpoOszlop.munkalap_id == m.id)
        .order_by(DiszpoOszlop.idx)
    ).all()
    sorok = db.scalars(
        select(DiszpoSor).where(DiszpoSor.munkalap_id == m.id).order_by(DiszpoSor.idx)
    ).all()
    cellak = db.execute(
        select(DiszpoCella.sor_idx, DiszpoCella.oszlop_idx, DiszpoCella.ertek, DiszpoCella.szin)
        .where(DiszpoCella.munkalap_id == m.id)
        .order_by(DiszpoCella.sor_idx, DiszpoCella.oszlop_idx)
    ).all()
    return MunkalapOut(
        **MunkalapFej.model_validate(m).model_dump(),
        oszlopok=[
            OszlopOut(
                idx=o.idx,
                cimke=o.cimke,
                csoport=o.csoport,
                employee_id=o.employee_id,
                employee_nev=o.employee.full_name if o.employee else None,
            )
            for o in oszlopok
        ],
        sorok=[
            SorOut(idx=s.idx, datum=s.datum, nap=s.nap, diszposzam=s.diszposzam, elvalaszto=s.elvalaszto)
            for s in sorok
        ],
        cellak=[(r, c, e, sz) for r, c, e, sz in cellak],
    )


class CellaIn(BaseModel):
    """Egy cella tartalma és/vagy színe.

    A `None` és a "nincs megadva" itt KÜLÖNBÖZIK: a szín törléséhez a `szin`
    mezőt kifejezetten `null`-ra kell állítani, míg a kihagyása azt jelenti,
    hogy maradjon, ami volt."""

    sor_idx: int
    oszlop_idx: int
    ertek: str | None = None
    szin: str | None = None
    #: Melyik mezőt akarjuk állítani. Enélkül egy szín-átállítás letörölné a
    #: cella szövegét (a felület a színpalettáról nem küld szöveget).
    ertek_valtozik: bool = False
    szin_valtozik: bool = False


@router.put("/{munkalap_id}/cella", response_model=MunkalapOut | None)
def set_cella(
    munkalap_id: int,
    payload: CellaIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy cella szerkesztése. Üres cellához nem tartozik sor - ha mindkét
    mezője kiürül, a sort töröljük."""
    m = _munkalap_vagy_404(db, munkalap_id)
    if payload.szin_valtozik and payload.szin is not None and payload.szin not in SZINEK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen szín. Választható: {', '.join(SZINEK)}")
    if not (0 <= payload.sor_idx < max(m.sor_szam, 1) + 500) or not (0 <= payload.oszlop_idx < m.oszlop_szam + 50):
        raise HTTPException(status_code=400, detail="A cella a munkalapon kívülre esik.")

    cella = db.scalar(
        select(DiszpoCella).where(
            DiszpoCella.munkalap_id == m.id,
            DiszpoCella.sor_idx == payload.sor_idx,
            DiszpoCella.oszlop_idx == payload.oszlop_idx,
        )
    )
    if cella is None:
        cella = DiszpoCella(munkalap_id=m.id, sor_idx=payload.sor_idx, oszlop_idx=payload.oszlop_idx)
        db.add(cella)
    if payload.ertek_valtozik:
        cella.ertek = (payload.ertek or "").strip() or None
    if payload.szin_valtozik:
        cella.szin = payload.szin
    if cella.ertek is None and cella.szin is None and cella.id is not None:
        db.delete(cella)
    # A szín MUNKANAP-ADAT: a következő önköltség-számítás már ezt lássa.
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


class OszlopKotesIn(BaseModel):
    """Melyik munkatárs oszlopa ez. `employee_id=None` = a kötés törlése."""

    employee_id: int | None = None


@router.put("/{munkalap_id}/oszlop/{idx}", response_model=OszlopOut)
def set_oszlop_kotes(
    munkalap_id: int,
    idx: int,
    payload: OszlopKotesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Az oszlop hozzákötése egy munkatárshoz.

    Enélkül az oszlop színei nem számítanak bele a munkanap-számlálásba: a
    "GERI" felirat nekünk nem azonosít senkit. Az import csak akkor köt, ha a
    név EGYÉRTELMŰ - a többit itt lehet megadni."""
    _munkalap_vagy_404(db, munkalap_id)
    oszlop = db.scalar(
        select(DiszpoOszlop).where(DiszpoOszlop.munkalap_id == munkalap_id, DiszpoOszlop.idx == idx)
    )
    if oszlop is None:
        raise HTTPException(status_code=404, detail="Ez az oszlop nem található.")
    if payload.employee_id is not None and db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=404, detail="Ez a munkatárs nem található.")
    oszlop.employee_id = payload.employee_id
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    db.refresh(oszlop)
    return OszlopOut(
        idx=oszlop.idx,
        cimke=oszlop.cimke,
        csoport=oszlop.csoport,
        employee_id=oszlop.employee_id,
        employee_nev=oszlop.employee.full_name if oszlop.employee else None,
    )


class HaviAllasOut(BaseModel):
    """Hol tart valaki a szerződött napjaival egy hónapban."""

    employee_id: int
    employee_nev: str | None = None
    ev: int
    honap: int
    munkanapok: int
    szerzodott_napok: int | None = None
    napi_dij: float | None = None
    plusz_nap_napi_dij: float | None = None
    #: Az a nap, amelyiken a szerződött napok elfogynak (az utolsó "benne van
    #: a bérben" nap). None, ha nincs napszám, vagy nem jött össze annyi nap.
    hatarnap: date | None = None
    #: A szerződött napokon FELÜLI munkanapok.
    plusz_napok: list[date] = []


@router.get("/munkanapok/{ev}/{honap}", response_model=list[HaviAllasOut])
def havi_allas(
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Ki hány napot dolgozott ebben a hónapban - és kinél fogyott el a
    szerződött napszám.

    Csak azok szerepelnek, akiknek van oszlopuk a diszpótáblában: akiről nincs
    adat, arról nem is állítunk semmit."""
    if not 1 <= honap <= 12:
        raise HTTPException(status_code=400, detail="A hónap 1 és 12 közötti szám.")
    employee_idk = set(munkanap_szamlalo.munkanap_terkep(db).keys())
    if not employee_idk:
        return []
    emberek = db.scalars(select(Employee).where(Employee.id.in_(employee_idk))).all()
    eredmeny: list[HaviAllasOut] = []
    for emb in emberek:
        kep = munkanap_szamlalo.havi_munkanapok(db, emb, ev, honap)
        if not kep.napok:
            continue
        eredmeny.append(
            HaviAllasOut(
                employee_id=emb.id,
                employee_nev=emb.full_name,
                ev=ev,
                honap=honap,
                munkanapok=kep.darab,
                szerzodott_napok=kep.szerzodott_napok,
                napi_dij=float(emb.napi_dij) if emb.napi_dij is not None else None,
                plusz_nap_napi_dij=float(emb.plusz_nap_napi_dij) if emb.plusz_nap_napi_dij is not None else None,
                hatarnap=kep.hatarnap,
                plusz_napok=kep.plusz_napok,
            )
        )
    eredmeny.sort(key=lambda a: (-a.munkanapok, a.employee_nev or ""))
    return eredmeny
