from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project
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


def _project_range(project: Project) -> tuple | None:
    if not project.forgatas_datuma:
        return None
    return project.forgatas_datuma, (project.forgatas_datuma_vege or project.forgatas_datuma)


def _ranges_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start <= b_end and b_start <= a_end


@assignments_router.get("", response_model=list[AssignmentRead])
def list_assignments(
    skip: int = 0,
    limit: int = 100,
    equipment_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    stmt = select(Assignment)
    if equipment_id is not None:
        stmt = stmt.where(Assignment.equipment_id == equipment_id)
    if project_id is not None:
        stmt = stmt.where(Assignment.project_id == project_id)
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@assignments_router.post(
    "",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db)):
    """Eszköz (Leltár, egyedi vagy darabszámos) hozzárendelése egy projekthez -
    ez a Leltár + Stock igények egységes hozzáadási mechanizmusa: 'asset' eszköznél
    qty=1, 'stock' eszköznél a kért darabszám. Az esetleges ütközést (más projekt
    ugyanarra az eszközre, átfedő napon, vagy a stock keret túllépése) NEM itt
    blokkoljuk - a projekten a 'Technika ready' ellenőrzés (POST
    /projects/{id}/technika-check) adja a hivatalos, nap-szintű riportot, ahogy az
    eredeti Notion workflow-ban is: szabadon fel lehet venni mindent, a checkbox
    futtatja le a validációt.

    Ha nincs megadva kivitel_datuma/visszahozatal_datuma, a projekt forgatási
    dátumaiból (forgatas_datuma / forgatas_datuma_vege) töltjük ki."""
    equipment = db.get(Equipment, payload.equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment nem található")
    project = db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")

    data = payload.model_dump()
    if data.get("kivitel_datuma") is None:
        data["kivitel_datuma"] = project.forgatas_datuma
    if data.get("visszahozatal_datuma") is None:
        data["visszahozatal_datuma"] = project.forgatas_datuma_vege or project.forgatas_datuma

    obj = Assignment(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@assignments_router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):
    obj = db.get(Assignment, assignment_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment nem található")
    db.delete(obj)
    db.commit()


@router.get("/{equipment_id}/availability")
def equipment_availability(
    equipment_id: int, project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    """Egy eszköz elérhetősége egy adott projekt forgatási napjaira - asset eszköznél
    foglalt-e már (más projekthez), stock eszköznél hány db szabad a teljes
    mennyiségből. A hozzáadás UI-ban ez mutatja élőben, mennyi elérhető, mielőtt
    a felhasználó ténylegesen hozzáadná."""
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment nem található")
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")

    project_range = _project_range(project)
    if project_range is None:
        return {"track_mode": equipment.track_mode.value, "available": None, "detail": "Nincs forgatási dátum a projekten."}
    start, end = project_range

    other_assignments = db.scalars(
        select(Assignment).where(Assignment.equipment_id == equipment_id, Assignment.project_id != project_id)
    ).all()

    if equipment.track_mode == TrackMode.ASSET:
        for a in other_assignments:
            other = db.get(Project, a.project_id)
            other_range = _project_range(other) if other else None
            if other_range and _ranges_overlap(start, end, *other_range):
                return {"track_mode": "asset", "available": False, "detail": f"Foglalt: {other.nev}"}
        return {"track_mode": "asset", "available": True, "detail": None}

    keret = equipment.osszes_mennyiseg or 0
    foglalt = 0
    for a in other_assignments:
        other = db.get(Project, a.project_id)
        other_range = _project_range(other) if other else None
        if other_range and _ranges_overlap(start, end, *other_range):
            foglalt += a.qty
    return {"track_mode": "stock", "available": max(keret - foglalt, 0), "keret": keret, "foglalt": foglalt}
