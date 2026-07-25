"""Admin végpont a HYPE CALENDAR naptár-szinkron kézi indításához/állapotának
megtekintéséhez - a percenkénti Celery Beat feladat (lásd workers/calendar_tasks.py)
mellett hasznos: azonnal tesztelhető anélkül, hogy az admin megvárná a
következő automatikus futást, és akkor is ad visszajelzést, ha a Celery
worker/beat még nincs (helyesen) deployolva."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.calendar_sync import CalendarSyncState
from app.models.employee import Employee
from app.services.google_calendar import (
    CalendarAuthError,
    CalendarNotConfiguredError,
    CalendarNotFoundError,
    sync_hype_calendar,
)

router = APIRouter(prefix="/admin/calendar-sync", tags=["admin"])


@router.post("")
def trigger_sync(db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    try:
        return sync_hype_calendar(db)
    except (CalendarNotConfiguredError, CalendarNotFoundError, CalendarAuthError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/status")
def get_status(db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    states = db.query(CalendarSyncState).all()
    return {
        "calendars": [
            {"calendar_id": s.calendar_id, "has_sync_token": s.sync_token is not None, "last_synced_at": s.updated_at}
            for s in states
        ]
    }
