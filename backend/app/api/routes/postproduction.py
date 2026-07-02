"""Utómunka modul: Deliverable (vágandó anyag) + Timesheet (ledolgozott idő) + Feedback (gombos visszajelzés)."""

from app.api.crud_router import build_crud_router
from app.models.deliverable import Deliverable
from app.models.feedback import Feedback
from app.models.timesheet import Timesheet
from app.schemas.deliverable import DeliverableCreate, DeliverableRead, DeliverableUpdate
from app.schemas.feedback import FeedbackCreate, FeedbackRead, FeedbackUpdate
from app.schemas.timesheet import TimesheetCreate, TimesheetRead, TimesheetUpdate

deliverables_router = build_crud_router(
    model=Deliverable,
    create_schema=DeliverableCreate,
    update_schema=DeliverableUpdate,
    read_schema=DeliverableRead,
    prefix="/deliverables",
    tags=["postproduction"],
)

timesheets_router = build_crud_router(
    model=Timesheet,
    create_schema=TimesheetCreate,
    update_schema=TimesheetUpdate,
    read_schema=TimesheetRead,
    prefix="/timesheets",
    tags=["postproduction"],
)

feedback_router = build_crud_router(
    model=Feedback,
    create_schema=FeedbackCreate,
    update_schema=FeedbackUpdate,
    read_schema=FeedbackRead,
    prefix="/feedback",
    tags=["postproduction"],
)
