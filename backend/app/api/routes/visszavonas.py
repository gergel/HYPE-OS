"""Törlés-visszavonás végpont (Ctrl+Z).

A generikus DELETE válasza tartalmazza a törlés-pillanatkép azonosítóját
(lásd crud_router.delete_item); a frontend Ctrl+Z-re ide POST-ol, és a sor
az eredeti id-jével visszakerül (lásd services/visszavonas.py).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee, SystemRole
from app.models.visszavonas import ToroltRekord
from app.services import visszavonas

router = APIRouter(prefix="/visszavonas", tags=["visszavonas"])


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
