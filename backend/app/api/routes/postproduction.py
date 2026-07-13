"""Utómunka modul: Deliverable (vágandó anyag) + Timesheet (ledolgozott idő) + Feedback (gombos visszajelzés)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.feedback import Feedback
from app.models.timesheet import Timesheet
from app.schemas.deliverable import DeliverableCreate, DeliverableListItem, DeliverableRead, DeliverableUpdate
from app.schemas.deliverable_actions import (
    AssignableEmployee,
    CommentCreate,
    CommentRead,
    ContactIdsPayload,
    ContactOption,
    TimerState,
    VinyoOptions,
)
from app.schemas.feedback import FeedbackCreate, FeedbackRead, FeedbackUpdate
from app.schemas.timesheet import TimesheetCreate, TimesheetRead, TimesheetUpdate
from app.services import deliverable_actions, notifications


def _after_deliverable_update(
    obj: Deliverable, data: dict, m2m_changes: dict, db: Session, current_user: Employee
) -> None:
    """Ha a PATCH kiosztotta (Assigned To) az anyagot valakinek, azt a
    munkatársat értesíti - lásd AssignedToPicker.tsx."""
    if "assigned_to_employee_id" not in data:
        return
    new_id = data["assigned_to_employee_id"]
    if not new_id:
        return
    title = obj.projekt_neve or f"Anyag #{obj.id}"
    notifications.create_notification(
        db,
        employee_id=new_id,
        kind="assignment",
        message=f"{current_user.full_name} kiosztotta neked: {title}",
        link=f"/utomunka/{obj.id}",
        actor_id=current_user.id,
    )
    db.commit()


deliverables_router = build_crud_router(
    model=Deliverable,
    create_schema=DeliverableCreate,
    update_schema=DeliverableUpdate,
    read_schema=DeliverableRead,
    list_read_schema=DeliverableListItem,
    prefix="/deliverables",
    tags=["postproduction"],
    page="/utomunka",
    after_update=_after_deliverable_update,
)

timesheets_router = build_crud_router(
    model=Timesheet,
    create_schema=TimesheetCreate,
    update_schema=TimesheetUpdate,
    read_schema=TimesheetRead,
    prefix="/timesheets",
    tags=["postproduction"],
    page="/utomunka",
)

feedback_router = build_crud_router(
    model=Feedback,
    create_schema=FeedbackCreate,
    update_schema=FeedbackUpdate,
    read_schema=FeedbackRead,
    prefix="/feedback",
    tags=["postproduction"],
    page="/utomunka",
)

# Külön router a Deliverable egyedi (nem CRUD) akcióihoz - FONTOS: ezt kell
# ELŐBB regisztrálni (lásd routes/__init__.py), mint a fenti deliverables_router-t,
# mert a generikus GET/PATCH/DELETE "/deliverables/{item_id}" route egyébként
# lenyelné az olyan statikus útvonalakat, mint "/deliverables/assignable-employees"
# (FastAPI/Starlette regisztrációs sorrendben próbálja a route-okat).
deliverable_actions_router = APIRouter(prefix="/deliverables", tags=["postproduction"])


def _get_deliverable_or_404(deliverable_id: int, db: Session) -> Deliverable:
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utómunka nem található")
    return deliverable


@deliverable_actions_router.get("/assignable-employees", response_model=list[AssignableEmployee])
def get_assignable_employees(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Kik jelölhetők ki az "Assigned To" mezőben - csak azok, akiknek van
    bejelentkezési joga és hozzáférése az /utomunka oldalhoz."""
    return deliverable_actions.list_assignable_employees(db)


@deliverable_actions_router.get("/vinyo-options", response_model=VinyoOptions)
def get_vinyo_options(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A valaha használt vinyó-értékek egyesített listája (choose-from lista a
    "Vinyók" többválasztós mezőhöz)."""
    return deliverable_actions.get_vinyo_options(db)


@deliverable_actions_router.get("/{deliverable_id}/contacts", response_model=list[ContactOption])
def get_deliverable_contacts(deliverable_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    return deliverable_actions.list_contacts(_get_deliverable_or_404(deliverable_id, db))


@deliverable_actions_router.put("/{deliverable_id}/contacts", response_model=list[ContactOption])
def set_deliverable_contacts(
    deliverable_id: int,
    payload: ContactIdsPayload,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Lecseréli a "Megrendelői kontaktok" listát, és újraszámolja a
    megrendeloi_email_cimek formula-mezőt."""
    deliverable = deliverable_actions.set_contacts(db, _get_deliverable_or_404(deliverable_id, db), payload.contact_ids)
    return deliverable_actions.list_contacts(deliverable)


@deliverable_actions_router.post("/{deliverable_id}/timer/start", status_code=status.HTTP_204_NO_CONTENT)
def start_timer(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    try:
        deliverable_actions.start_timer(db, _get_deliverable_or_404(deliverable_id, db), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deliverable_actions_router.post("/{deliverable_id}/timer/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_timer(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    try:
        deliverable_actions.stop_timer(db, _get_deliverable_or_404(deliverable_id, db), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@deliverable_actions_router.get("/{deliverable_id}/timer/state", response_model=TimerState)
def get_timer_state(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    return deliverable_actions.get_timer_state(db, _get_deliverable_or_404(deliverable_id, db), current_user)


@deliverable_actions_router.post("/{deliverable_id}/kuldes-visszajelzes", response_model=FeedbackRead)
def send_visszajelzes(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """"Visszajelzés küldése" gomb - lásd services/deliverable_actions.send_visszajelzes."""
    return deliverable_actions.send_visszajelzes(db, _get_deliverable_or_404(deliverable_id, db), current_user)


@deliverable_actions_router.get("/{deliverable_id}/comments", response_model=list[CommentRead])
def get_comments(deliverable_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    _get_deliverable_or_404(deliverable_id, db)
    return deliverable_actions.list_comments(db, deliverable_id)


@deliverable_actions_router.post("/{deliverable_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def post_comment(
    deliverable_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    _get_deliverable_or_404(deliverable_id, db)
    if not payload.body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A hozzászólás nem lehet üres")
    return deliverable_actions.add_comment(db, deliverable_id, current_user, payload.body.strip())
