"""Törlés-visszavonás végpont (Ctrl+Z).

A generikus DELETE válasza tartalmazza a törlés-pillanatkép azonosítóját
(lásd crud_router.delete_item); a frontend Ctrl+Z-re ide POST-ol, és a sor
az eredeti id-jével visszakerül (lásd services/visszavonas.py).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.employee import Employee, SystemRole
from app.models.visszavonas import ToroltRekord
from app.services import visszavonas

router = APIRouter(prefix="/visszavonas", tags=["visszavonas"])

#: Ezekből a mezőkből próbáljuk kiolvasni, MI volt a törölt rekord - a
#: napló-listán egy "projects #42" önmagában semmit nem mondana.
_NEV_MEZOK = ("nev", "projekt_neve", "full_name", "title", "name", "feladat", "cim", "targy", "projektkod", "filename")


class TorlesSor(BaseModel):
    """Egy törlés a tevékenység-előzményekben (admin nézet)."""

    id: int
    tabla: str
    rekord_id: int
    #: A törölt rekord neve/címe a pillanatképből (ha kiolvasható).
    megnevezes: str | None = None
    torolte: str | None = None
    mikor: datetime
    visszaallitva: bool


@router.get("/torlesek", response_model=list[TorlesSor], dependencies=[Depends(require_roles(Role.ADMIN))])
def torlesek(db: Session = Depends(get_db)):
    """TEVÉKENYSÉG-ELŐZMÉNYEK (a felhasználó kérése): minden törlés, amit a
    rendszer pillanatképpel őriz (30 napig, lásd services/visszavonas) - ki,
    mikor, mit törölt, és visszaállítható-e még. CSAK admin láthatja."""
    sorok = db.scalars(select(ToroltRekord).order_by(ToroltRekord.created_at.desc()).limit(500)).all()
    nevek = {
        e.id: e.full_name
        for e in db.scalars(
            select(Employee).where(Employee.id.in_({s.employee_id for s in sorok if s.employee_id}))
        ).all()
    }

    def megnevezes(adatok: dict) -> str | None:
        for kulcs in _NEV_MEZOK:
            ertek = (adatok or {}).get(kulcs)
            if isinstance(ertek, str) and ertek.strip():
                return ertek.strip()[:120]
        return None

    return [
        TorlesSor(
            id=s.id,
            tabla=s.tabla,
            rekord_id=s.rekord_id,
            megnevezes=megnevezes(s.adatok),
            torolte=nevek.get(s.employee_id) if s.employee_id else None,
            mikor=s.created_at,
            visszaallitva=s.visszaallitva,
        )
        for s in sorok
    ]


@router.post("/torles/{pillanatkep_id}")
def torles_visszavonasa(
    pillanatkep_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Csak az vonhatja vissza, aki törölt (vagy admin) - a törléshez a jog
    már megvolt, a visszavonás ugyanannak a mozdulatnak a visszája."""
    pillanatkep = db.get(ToroltRekord, pillanatkep_id)
    if pillanatkep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen visszavonható törlés.")
    if pillanatkep.employee_id != current_user.id and current_user.role != SystemRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ezt a törlést más végezte - csak ő (vagy admin) vonhatja vissza.",
        )
    try:
        visszavonas.allitsd_vissza(db, pillanatkep)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"ok": True, "tabla": pillanatkep.tabla, "rekord_id": pillanatkep.rekord_id}
