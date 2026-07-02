from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.equipment import Assignment, Equipment, TrackMode
from app.schemas.equipment import (
    AssignmentCreate,
    AssignmentRead,
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
)

router = build_crud_router(
    model=Equipment,
    create_schema=EquipmentCreate,
    update_schema=EquipmentUpdate,
    read_schema=EquipmentRead,
    prefix="/equipment",
    tags=["equipment"],
)

assignments_router = APIRouter(prefix="/assignments", tags=["equipment"])


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    """Két dátumtartomány átfedésben van-e - nyitott végű (None) tartomány = 'még kint van'."""
    if a_end is not None and b_start is not None and a_end < b_start:
        return False
    if b_end is not None and a_start is not None and b_end < a_start:
        return False
    return True


@assignments_router.get("", response_model=list[AssignmentRead])
def list_assignments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.scalars(select(Assignment).offset(skip).limit(limit)).all()


@assignments_router.post(
    "",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db)):
    """Ütközés-detektálás a HYPE_Technika minta alapján: 'asset' eszköznél egy adott
    időszakban csak egy aktív kiadás lehet; 'stock' eszköznél a lefoglalt darabszám
    nem lépheti túl az összes mennyiséget.
    """
    equipment = db.get(Equipment, payload.equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment nem található")

    existing = db.scalars(select(Assignment).where(Assignment.equipment_id == payload.equipment_id)).all()
    overlapping = [
        a
        for a in existing
        if _overlaps(a.kivitel_datuma, a.visszahozatal_datuma, payload.kivitel_datuma, payload.visszahozatal_datuma)
    ]

    if equipment.track_mode == TrackMode.ASSET:
        if overlapping:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ütközés: '{equipment.nev}' már ki van adva ebben az időszakban (assignment id={overlapping[0].id})",
            )
    else:
        foglalt = sum(a.qty for a in overlapping)
        keret = equipment.osszes_mennyiseg or 0
        if foglalt + payload.qty > keret:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ütközés: '{equipment.nev}' készlet túllépve ({foglalt + payload.qty}/{keret} db ebben az időszakban)",
            )

    obj = Assignment(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
