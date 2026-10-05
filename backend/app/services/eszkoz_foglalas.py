"""Eszköz hozzárendelése egy projekthez (Assignment) - a KÖZÖS út.

Ugyanezt használja a felület (POST /assignments, routes/equipment.py) és Lara
technikai-lista végrehajtója (admin_agent/diszpo_tervezo.py), hogy a kettő
pontosan ugyanúgy viselkedjen:

- a kivitel/visszahozatal dátuma alapból a forgatás napjai;
- UGYANAZ az eszköz ugyanarra a projektre és időszakra nem kap új sort:
  készletes (stock) eszköznél a darabszám adódik hozzá, egyedi (asset)
  eszköznél a meglévő sor marad változatlanul;
- ütközést itt NEM blokkolunk - a hivatalos, nap-szintű riportot a
  „Technika ready” ellenőrzés adja (services/technika.check_technika);
- ARCHIVÁLT eszköz nem foglalható (ArchivaltEszkoz) - a múltbeli foglalásai
  megmaradnak, csak újat nem lehet rá tenni.

A hívó commitol."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project


class ArchivaltEszkoz(ValueError):
    """Archivált eszközt nem lehet forgatásra foglalni / kiírni."""

    def __init__(self, equipment: Equipment):
        super().__init__(
            f"„{equipment.nev}” archivált eszköz - nem foglalható forgatásra. "
            "Ha mégis kell, előbb állítsd vissza a Felszerelés oldalon."
        )


def hozzarendel(
    db: Session,
    project: Project,
    equipment: Equipment,
    *,
    qty: int = 1,
    kivitel_datuma: date | None = None,
    visszahozatal_datuma: date | None = None,
    **tovabbi,
) -> tuple[Assignment, str]:
    """Vissza: (a foglalás sora, mi történt: "uj" | "novelve" | "mar_megvolt").
    Archivált eszköznél ArchivaltEszkoz."""
    if equipment.archivalva_at is not None:
        raise ArchivaltEszkoz(equipment)
    kivitel = kivitel_datuma or project.forgatas_datuma
    visszahozatal = visszahozatal_datuma or project.forgatas_datuma_vege or project.forgatas_datuma
    meglevo = db.scalar(
        select(Assignment).where(
            Assignment.equipment_id == equipment.id,
            Assignment.project_id == project.id,
            Assignment.kivitel_datuma == kivitel,
            Assignment.visszahozatal_datuma == visszahozatal,
        )
    )
    stock = equipment.track_mode in (TrackMode.STOCK, "stock")
    if meglevo is not None:
        if stock:
            meglevo.qty = (meglevo.qty or 0) + (qty or 1)
            db.flush()
            return meglevo, "novelve"
        return meglevo, "mar_megvolt"
    obj = Assignment(
        equipment_id=equipment.id,
        project_id=project.id,
        qty=qty or 1,
        kivitel_datuma=kivitel,
        visszahozatal_datuma=visszahozatal,
        **tovabbi,
    )
    db.add(obj)
    db.flush()
    return obj, "uj"
