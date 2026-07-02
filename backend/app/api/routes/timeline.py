"""Timeline modul: esemény-napló minden entitáshoz - az Automation service írja."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.timeline import TimelineEvent
from app.schemas.timeline import TimelineEventCreate, TimelineEventRead

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("", response_model=list[TimelineEventRead])
def list_events(
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    stmt = select(TimelineEvent).order_by(TimelineEvent.created_at.desc())
    if entity_type:
        stmt = stmt.where(TimelineEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(TimelineEvent.entity_id == entity_id)
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@router.post("", response_model=TimelineEventRead, status_code=201)
def create_event(payload: TimelineEventCreate, db: Session = Depends(get_db)):
    obj = TimelineEvent(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
