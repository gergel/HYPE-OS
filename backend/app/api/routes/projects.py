from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.employee import Employee
from app.models.project import Project
from app.schemas.deliverable import DeliverableRead
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_actions import create_feldarabolas, create_utomunka
from app.services.technika import check_technika

router = build_crud_router(
    model=Project,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    read_schema=ProjectRead,
    prefix="/projects",
    tags=["projects"],
    m2m_fields={"crew_employee_ids": ("crew", Employee)},
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")
    return project


@router.post(
    "/{project_id}/technika-check",
    tags=["projects"],
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def run_technika_check(project_id: int, db: Session = Depends(get_db)):
    """A 'Technika ready' gomb - lefuttatja az eszköz-ütközés ellenőrzést a
    projekthez rendelt (Assignment) eszközökre, és visszaírja az eredményt
    (technika_lista, backend_statusz, backend_uzenet)."""
    return check_technika(db, _get_project_or_404(project_id, db))


@router.post("/{project_id}/feldarabolas", response_model=ProjectRead, tags=["projects"])
def run_feldarabolas(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN, Role.OPERATOR))):
    """A 'Feldarabolás' gomb - új Project sort hoz létre ugyanahhoz a Project
    Code-hoz, átmásolva a nevet/leírást/projektkódot/stábot (lásd
    app/services/project_actions.py)."""
    return create_feldarabolas(db, _get_project_or_404(project_id, db))


@router.post("/{project_id}/create-utomunka", response_model=DeliverableRead, tags=["projects"])
def run_create_utomunka(
    project_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(require_roles(Role.ADMIN, Role.OPERATOR))
):
    """Az 'Utómunka' gomb - új Deliverable-t hoz létre ehhez a projekthez, a Notion
    automatizmussal megegyező névképzéssel (lásd app/services/project_actions.py)."""
    return create_utomunka(db, _get_project_or_404(project_id, db), current_user)
