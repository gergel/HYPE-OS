from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class CalendarSyncState(TimestampMixin, Base):
    """A Google Calendar API inkrementális szinkronjának állapota naptáranként
    (jelenleg csak a HYPE CALENDAR-hoz van sor) - a sync_token birtokában a
    percenkénti sync feladat csak a legutóbbi futás óta VÁLTOZOTT eseményeket
    kéri le (nem az egész naptárat újra), lásd services/google_calendar.py.
    Ha a token lejár/érvénytelenné válik (Google 410 GONE-t ad), a szinkron
    törli és null-ra állítja, ami a következő futásnál teljes újraszinkront vált ki."""

    __tablename__ = "calendar_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    sync_token: Mapped[str | None] = mapped_column(Text)
