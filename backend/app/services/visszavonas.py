"""A törlés-visszavonás (Ctrl+Z) szolgáltatása.

Két fele van:
 - mentsd_a_torlest: a generikus törlés (crud_router) hívja a db.delete
   ELŐTT - a rekord sima oszlopait JSON-békévé alakítva elteszi a
   torolt_rekordok táblába, és a pillanatkép id-jét adja vissza (ezt kapja
   meg a frontend a DELETE válaszában);
 - allitsd_vissza: a pillanatképből visszateszi a sort UGYANAZZAL az id-vel,
   így a rá mutató, még élő hivatkozások is újra működnek. A kaszkáddal
   törölt kapcsolt sorokat nem hozza vissza - ez a "gyors visszavonás" egy
   véletlen kattintás ellen, nem teljes biztonsági mentés.
"""

from __future__ import annotations

import enum
import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.employee import Employee
from app.models.visszavonas import ToroltRekord

logger = logging.getLogger("hype_os")

#: Ennyi ideig őrizzük a pillanatképeket - a Ctrl+Z jellemzően másodperceken
#: belül jön, a 30 nap bőven elég, és a tábla nem hízik a végtelenségig.
_MEGORZES = timedelta(days=30)


def _json_bekeve(ertek):
    """Egy oszlop-érték JSON-ba tehető alakja (dátum -> ISO szöveg, Decimal ->
    float, enum -> az értéke). A Postgres a visszaszúráskor az ISO szöveget
    magától visszaalakítja a megfelelő oszloptípusra."""
    if isinstance(ertek, (datetime, date, time)):
        return ertek.isoformat()
    if isinstance(ertek, Decimal):
        return float(ertek)
    if isinstance(ertek, enum.Enum):
        return ertek.value
    return ertek


def mentsd_a_torlest(db: Session, model: type, obj, current_user: Employee | None) -> int | None:
    """A törlendő rekord pillanatképe. Ha bármi miatt nem sikerül (pl. nem
    JSON-osítható érték), csak naplózunk - a törlést nem buktathatja meg,
    ilyenkor egyszerűen nem lesz visszavonható."""
    try:
        adatok = {oszlop.name: _json_bekeve(getattr(obj, oszlop.name, None)) for oszlop in model.__table__.columns}
        pillanatkep = ToroltRekord(
            tabla=model.__tablename__,
            rekord_id=obj.id,
            adatok=adatok,
            employee_id=current_user.id if current_user is not None else None,
        )
        db.add(pillanatkep)
        # A lejárt pillanatképek takarítása - itt, mert ide írunk úgyis.
        db.execute(sa_delete(ToroltRekord).where(ToroltRekord.created_at < datetime.now(timezone.utc) - _MEGORZES))
        db.flush()
        return pillanatkep.id
    except Exception:  # noqa: BLE001 - a törlés e nélkül is menjen végig
        logger.exception("Nem sikerült pillanatképet menteni a törléshez (%s #%s)", model.__name__, getattr(obj, "id", "?"))
        return None


def _modell_tablanev_szerint(tabla: str) -> type | None:
    for mapper in Base.registry.mappers:
        if getattr(mapper.class_, "__tablename__", None) == tabla:
            return mapper.class_
    return None


def allitsd_vissza(db: Session, pillanatkep: ToroltRekord) -> None:
    """A pillanatkép visszaszúrása az eredeti táblába, az eredeti id-vel.
    ValueError-t dob érthető magyar üzenettel, ha nem lehetséges."""
    if pillanatkep.visszaallitva:
        raise ValueError("Ezt a törlést már visszavonták.")
    model = _modell_tablanev_szerint(pillanatkep.tabla)
    if model is None:
        raise ValueError(f"Ismeretlen tábla a pillanatképben: {pillanatkep.tabla}")
    letezo = db.scalar(select(model.__table__.c.id).where(model.__table__.c.id == pillanatkep.rekord_id))
    if letezo is not None:
        raise ValueError("A rekord már létezik - nincs mit visszaállítani.")
    # Csak a MA IS létező oszlopokat szúrjuk vissza: ha a séma azóta bővült,
    # az új oszlop az alapértelmezettjét kapja; ha szűkült, a régi érték kimarad.
    oszlopok = {c.name for c in model.__table__.columns}
    adatok = {k: v for k, v in (pillanatkep.adatok or {}).items() if k in oszlopok}
    db.execute(model.__table__.insert().values(**adatok))
    pillanatkep.visszaallitva = True
