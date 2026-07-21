from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.employee import Employee
from app.models.project import Project
from app.schemas.deliverable import DeliverableRead
from app.schemas.project import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate, SzerzodesKeszitesPayload
from app.services.contract_actions import apply_szerzodes_keszites, send_szerzodes
from app.services.dispo import send_diszpo, send_elozetes_diszpo
from app.services.project_actions import create_feldarabolas, create_utomunka
from app.services.technika import check_technika

router = build_crud_router(
    model=Project,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    read_schema=ProjectRead,
    list_read_schema=ProjectListItem,
    prefix="/projects",
    tags=["projects"],
    page="/projektek",
    m2m_fields={"crew_employee_ids": ("crew", Employee)},
    entity_type="project",
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


def _run_dispatch_action(action, *args):
    """A diszpó/szerződés küldő akciók (Gmail/Google Docs hívást igényelnek) közös
    hibakezelése: ValueError -> 400 (pl. hiányzó címzett), RuntimeError -> 503
    (hiányzó Google hitelesítő adat - csak Railway-en, valódi env varokkal
    tesztelhető, lásd app/services/google_email.py)."""
    try:
        return action(*args)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/{project_id}/diszpo/elozetes", tags=["projects"])
def run_elozetes_diszpo(
    project_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(require_roles(Role.ADMIN, Role.OPERATOR))
):
    """'Előzetes diszpó' gomb (lásd app/services/dispo.py)."""
    return _run_dispatch_action(send_elozetes_diszpo, db, _get_project_or_404(project_id, db), current_user)


@router.post("/{project_id}/diszpo/kuldes", tags=["projects"])
def run_diszpo_kuldes(
    project_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(require_roles(Role.ADMIN, Role.OPERATOR))
):
    """'Diszpó küldése' gomb (lásd app/services/dispo.py)."""
    return _run_dispatch_action(send_diszpo, db, _get_project_or_404(project_id, db), current_user)


@router.post(
    "/{project_id}/szerzodes-keszites",
    response_model=ProjectRead,
    tags=["projects"],
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def run_szerzodes_keszites(project_id: int, payload: SzerzodesKeszitesPayload, db: Session = Depends(get_db)):
    """'Szerződés készítés' relation (Külsős és belsős) - a kiválasztott ember adatai
    a Project megbízott_* mezőibe másolódnak (lásd app/services/contract_actions.py)."""
    try:
        return apply_szerzodes_keszites(db, _get_project_or_404(project_id, db), payload.employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{project_id}/szerzodes-keszites-es-kuldese",
    tags=["projects"],
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def run_szerzodes_kuldes(project_id: int, db: Session = Depends(get_db)):
    """'szerződés készítése és küldése' gomb (lásd app/services/contract_actions.py)."""
    return _run_dispatch_action(send_szerzodes, db, _get_project_or_404(project_id, db))
