"""LEHETSÉGES DUPLIKÁCIÓ a kiadás felvezetésekor (a felhasználó kérése,
2026-10): ha ugyanarra a DÁTUMRA, ugyanarra az ÖSSZEGRE és ugyanarra a
CÉGRE már van felvezetett kiadás, a mentés előtt szólunk - az ember
ellenőrzi, és vagy MÉGIS felviszi (`duplikacio_engedve`), vagy elveti.

Mi számít egyezésnek:

- dátum: a kiadás egyetlen dátuma (`fizetes_datuma`) pontosan egyezik;
- összeg: a bruttó (ha nincs, a nettó) legfeljebb 1 Ft-tal tér el - forintra
  váltva, ugyanúgy, ahogy elmentenénk;
- cég: a „Cégnév” (`megnevezes`) kis-/nagybetűtől, ékezettől és szóközöktől
  függetlenül egyezik, VAGY ugyanaz a munkatárs (`employee_id`, külsős tétel).

Dátum vagy összeg nélkül nem ellenőrzünk (nincs mihez mérni)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Expense
from app.services.hu_szoveg import ekezet_nelkul

KOD = "lehetseges_duplikacio"
ENGEDES_MEZO = "duplikacio_engedve"
TURES = Decimal("1")


def _ceg_kulcs(nev: Any) -> str:
    return " ".join(ekezet_nelkul(str(nev or "")).split())


def _szam(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return None


def lehetseges_duplikaciok(db: Session, adat: dict) -> list[Expense]:
    """A felvenni kívánt kiadással (dátum + összeg + cég) egyező meglévő kiadások."""
    datum = adat.get("fizetes_datuma")
    if isinstance(datum, str):
        try:
            datum = date.fromisoformat(datum[:10])
        except ValueError:
            datum = None
    brutto, netto = _szam(adat.get("brutto")), _szam(adat.get("netto"))
    if datum is None or (brutto is None and netto is None):
        return []
    ceg = _ceg_kulcs(adat.get("megnevezes"))
    employee_id = adat.get("employee_id")
    if not ceg and not employee_id:
        return []

    osszeg_feltetel = []
    if brutto is not None:
        osszeg_feltetel.append(and_(Expense.brutto.is_not(None), func.abs(Expense.brutto - brutto) <= TURES))
    if netto is not None:
        osszeg_feltetel.append(and_(Expense.netto.is_not(None), func.abs(Expense.netto - netto) <= TURES))
    jeloltek = db.scalars(
        select(Expense)
        .where(Expense.fizetes_datuma == datum, or_(*osszeg_feltetel))
        .options(selectinload(Expense.project_code))
        .order_by(Expense.id)
    ).all()
    return [
        e for e in jeloltek
        if (ceg and _ceg_kulcs(e.megnevezes) == ceg) or (employee_id and e.employee_id == employee_id)
    ]


def ellenoriz(db: Session, adat: dict) -> None:
    """A létrehozás előtt: egyezés esetén 409 a találatokkal - kivéve, ha az
    ember már megnézte és engedte (`duplikacio_engedve`). A jelzőt mindig
    kivesszük az adatból (nem modell-mező)."""
    if adat.pop(ENGEDES_MEZO, False):
        return
    talalatok = lehetseges_duplikaciok(db, adat)
    if not talalatok:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "kod": KOD,
            "uzenet": (
                "Erre a dátumra, ugyanezzel az összeggel és céggel már van felvezetett kiadás. "
                "Ellenőrizd, nem ugyanaz-e - ha nem, mégis felviheted."
            ),
            "tetelek": [
                {
                    "id": e.id,
                    "megnevezes": e.megnevezes,
                    "kiadas_leiras": e.kiadas_leiras,
                    "brutto": float(e.brutto) if e.brutto is not None else None,
                    "netto": float(e.netto) if e.netto is not None else None,
                    "fizetes_datuma": e.fizetes_datuma.isoformat() if e.fizetes_datuma else None,
                    "projektkod": e.project_code.projektkod if e.project_code else None,
                    "href": f"/penzugyek/kiadas/{e.id}",
                }
                for e in talalatok[:10]
            ],
        },
    )
