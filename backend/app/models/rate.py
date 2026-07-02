from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Rate(TimestampMixin, Base):
    """Bérezési szabály - az önköltség-számítás motorja (Employee -> Rate)."""

    __tablename__ = "rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)

    orabler: Mapped[float | None] = mapped_column(Numeric(12, 2))
    napibler: Mapped[float | None] = mapped_column(Numeric(12, 2))
    tulora: Mapped[float | None] = mapped_column(Numeric(12, 2))
    plusz_nap: Mapped[float | None] = mapped_column(Numeric(12, 2))
    havi_alap: Mapped[float | None] = mapped_column(Numeric(12, 2))

    elso_munkanap: Mapped[date | None] = mapped_column(Date)
    utolso_munkanap: Mapped[date | None] = mapped_column(Date)

    employee: Mapped["Employee"] = relationship(back_populates="rates")
