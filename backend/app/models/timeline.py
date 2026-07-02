from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class TimelineEvent(TimestampMixin, Base):
    """Esemény-napló minden entitáshoz - az Automation modul írja (pl. DeliverableApproved)."""

    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
