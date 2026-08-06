"""Utómunka modul: Deliverable (vágandó anyag) + Timesheet (ledolgozott idő) + Feedback (gombos visszajelzés)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import (
    Role,
    ellenorizd_anyag_hozzaferest,
    get_current_user,
    lathato_anyagok,
    require_page_action,
    require_roles,
)
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


def _csak_a_sajat_anyagai(stmt, db: Session, user: Employee):
    """Sorszűrő a korlátozott fiókokhoz: egy külsős vágó csak azt az anyagot
    látja, amire behívtuk (lásd core/security.lathato_anyagok). Aki nincs
    korlátozva, annak a lekérdezés változatlan."""
    engedett = lathato_anyagok(db, user)
    if engedett is None:
        return stmt
    return stmt.where(Deliverable.id.in_(engedett or {0}))


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
    entity_type="deliverable",
    sor_szuro=_csak_a_sajat_anyagai,
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


def _get_deliverable_or_404(deliverable_id: int, db: Session, user: Employee | None = None) -> Deliverable:
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utómunka nem található")
    if user is not None:
        # A korlátozott fiók (külsős vágó) csak a saját anyagán dolgozhat -
        # az akció-végpontokra ugyanaz a szűkítés vonatkozik, mint a listára.
        ellenorizd_anyag_hozzaferest(db, user, deliverable_id)
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
def get_deliverable_contacts(
    deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)
):
    return deliverable_actions.list_contacts(_get_deliverable_or_404(deliverable_id, db, current_user))


@deliverable_actions_router.put("/{deliverable_id}/contacts", response_model=list[ContactOption])
def set_deliverable_contacts(
    deliverable_id: int,
    payload: ContactIdsPayload,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Lecseréli a "Megrendelői kontaktok" listát, és újraszámolja a
    megrendeloi_email_cimek formula-mezőt."""
    deliverable = deliverable_actions.set_contacts(db, _get_deliverable_or_404(deliverable_id, db, current_user), payload.contact_ids)
    return deliverable_actions.list_contacts(deliverable)


@deliverable_actions_router.post("/{deliverable_id}/timer/start", status_code=status.HTTP_204_NO_CONTENT)
def start_timer(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    try:
        deliverable_actions.start_timer(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deliverable_actions_router.post("/{deliverable_id}/timer/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_timer(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    try:
        deliverable_actions.stop_timer(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@deliverable_actions_router.post(
    "/{deliverable_id}/timer/stop/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def stop_timer_for_employee(
    deliverable_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """MÁS ember futó időmérésének leállítása - csak adminnak. Egy elfelejtett
    mérőt egyébként csak az tudna lezárni, aki elindította; ha ő nincs gépnél,
    egész éjjel futna (és a belőle számolt költség is hibás lenne)."""
    try:
        deliverable_actions.stop_timer(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@deliverable_actions_router.get("/{deliverable_id}/timer/state", response_model=TimerState)
def get_timer_state(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    return deliverable_actions.get_timer_state(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)


@deliverable_actions_router.post("/{deliverable_id}/kuldes-visszajelzes", response_model=FeedbackRead)
def send_visszajelzes(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """"Visszajelzés küldése" gomb - lásd services/deliverable_actions.send_visszajelzes."""
    return deliverable_actions.send_visszajelzes(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)


class PercekIn(BaseModel):
    """Percek egy már rögzített munkaidő-sorra - lásd set_timesheet_minutes."""

    minutes: float


@deliverable_actions_router.post("/{deliverable_id}/timesheets/{timesheet_id}/percek", response_model=TimesheetRead)
def set_timesheet_minutes(
    deliverable_id: int,
    timesheet_id: int,
    payload: PercekIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/utomunka", "edit")),
):
    """Egy munkaidő-sor percének UTÓLAGOS javítása - ha valaki elfelejtette
    leállítani az időmérőt (pl. egész éjjel futott), ez az egyetlen módja, hogy
    a valós munkaidő kerüljön be. A költséget is újraszámoljuk az akkori
    órabérrel, különben a Pénzügyben a hibás összeg maradna."""
    if payload.minutes < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A perc nem lehet negatív.")
    row = db.get(Timesheet, timesheet_id)
    if row is None or row.deliverable_id != deliverable_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen munkaidő-elszámolás ezen az anyagon.")
    row.time_minutes = payload.minutes
    # Az órabér a sor SAJÁT, befagyasztott órabére (akkori_orabere) - egy
    # későbbi béremelés a régi költséget nem írhatja át. Ha még nincs rögzítve,
    # most vesszük fel a mostanit.
    if row.akkori_orabere is None:
        row.akkori_orabere = deliverable_actions.aktualis_orabere(db, row.employee_id)
    row.koltseg = deliverable_actions.szamolt_koltseg(payload.minutes, row.akkori_orabere)
    db.commit()
    db.refresh(row)
    return row


@deliverable_actions_router.get("/{deliverable_id}/comments", response_model=list[CommentRead])
def get_comments(
    deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)
):
    _get_deliverable_or_404(deliverable_id, db, current_user)
    return deliverable_actions.list_comments(db, deliverable_id)


@deliverable_actions_router.post("/{deliverable_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def post_comment(
    deliverable_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    _get_deliverable_or_404(deliverable_id, db, current_user)
    if not payload.body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A hozzászólás nem lehet üres")
    return deliverable_actions.add_comment(db, deliverable_id, current_user, payload.body.strip())
