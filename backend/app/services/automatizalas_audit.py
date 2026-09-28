"""Automatizálási audit-napló - az automatikus műveletek és a gépi
adategyeztetések (AI-kiolvasás, szabály alapú besorolás, Lara) nyoma.

Szándékosan egyetlen belépési pont (`naplo`), hogy a hívók ne írhassanak
tetszőleges mezőt, és a részletekből kiszűrjük az érzékeny adatot: a napló
azt rögzíti, MIT javasolt a gép és MI lett belőle, nem a dokumentum
tartalmát. Csak hozzáfűzés: nincs módosító vagy törlő függvény."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automatizalas import SZEREPLOK, AutomatizalasAudit

#: Ezek a kulcsok sosem kerülhetnek a naplóba - akkor sem, ha a hívó
#: véletlenül a teljes bemenetet adja át.
TILTOTT_KULCSOK = frozenset(
    {
        "bankszamlaszam",
        "bankszamla",
        "iban",
        "jelszo",
        "token",
        "api_kulcs",
        "email_szoveg",
        "szoveg_teljes",
        "fajl",
        "adat",
    }
)
_MAX_SZOVEG = 500


def _tisztit(ertek: Any, melyseg: int = 0) -> Any:
    if melyseg > 6:
        return "…"
    if isinstance(ertek, dict):
        return {
            str(k): _tisztit(v, melyseg + 1) for k, v in ertek.items() if str(k).lower() not in TILTOTT_KULCSOK
        }
    if isinstance(ertek, (list, tuple)):
        return [_tisztit(v, melyseg + 1) for v in list(ertek)[:50]]
    if isinstance(ertek, str):
        return ertek if len(ertek) <= _MAX_SZOVEG else ertek[:_MAX_SZOVEG] + "…"
    if isinstance(ertek, (int, float, bool)) or ertek is None:
        return ertek
    return str(ertek)


def naplo(
    db: Session,
    *,
    muvelet: str,
    eroforras_tipus: str,
    eroforras_id: int | None,
    szereplo: str = "rendszer",
    employee_id: int | None = None,
    eredmeny: str = "ok",
    reszletek: dict | None = None,
) -> AutomatizalasAudit:
    """Egy naplósor hozzáadása a hívó tranzakciójához (a hívó commitol - így
    a napló és a naplózott változás együtt marad meg vagy együtt vész el)."""
    if szereplo not in SZEREPLOK:
        raise ValueError(f"Ismeretlen szereplő: {szereplo}")
    sor = AutomatizalasAudit(
        muvelet=muvelet[:60],
        eroforras_tipus=eroforras_tipus[:40],
        eroforras_id=eroforras_id,
        szereplo=szereplo,
        employee_id=employee_id,
        eredmeny=eredmeny[:20],
        reszletek=_tisztit(reszletek) if reszletek else None,
    )
    db.add(sor)
    db.flush()
    return sor


def lista(
    db: Session, *, eroforras_tipus: str | None = None, eroforras_id: int | None = None, limit: int = 100
) -> list[AutomatizalasAudit]:
    q = select(AutomatizalasAudit)
    if eroforras_tipus is not None:
        q = q.where(AutomatizalasAudit.eroforras_tipus == eroforras_tipus)
    if eroforras_id is not None:
        q = q.where(AutomatizalasAudit.eroforras_id == eroforras_id)
    q = q.order_by(AutomatizalasAudit.tortent_at.desc(), AutomatizalasAudit.id.desc()).limit(max(1, min(limit, 500)))
    return list(db.scalars(q).all())


def sor_dict(sor: AutomatizalasAudit) -> dict:
    return {
        "id": sor.id,
        "tortent_at": sor.tortent_at.isoformat() if sor.tortent_at else None,
        "szereplo": sor.szereplo,
        "employee_id": sor.employee_id,
        "muvelet": sor.muvelet,
        "eroforras_tipus": sor.eroforras_tipus,
        "eroforras_id": sor.eroforras_id,
        "eredmeny": sor.eredmeny,
        "reszletek": sor.reszletek,
    }
