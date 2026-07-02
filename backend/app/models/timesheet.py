from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Timesheet(TimestampMixin, Base):
    """Ledolgozott idő - vágási óraköltség számításhoz (Rate x óra)."""

    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    deliverable_id: Mapped[int | None] = mapped_column(ForeignKey("deliverables.id"))

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    koltseg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    statusz: Mapped[str | None] = mapped_column(String(50))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    employee: Mapped["Employee"] = relationship(back_populates="timesheets")
    deliverable: Mapped["Deliverable"] = relationship(back_populates="timesheets")

    @property
    def idotartam_perc(self) -> int | None:
        if self.start_date is None or self.end_date is None:
            return None
        return int((self.end_date - self.start_date).total_seconds() // 60)
