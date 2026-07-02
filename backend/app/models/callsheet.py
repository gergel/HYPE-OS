from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Callsheet(TimestampMixin, Base):
    """Diszpó - projekt-eseménynapló, két fokozatú email-szál (előzetes/teljes) az Automation modulban."""

    __tablename__ = "callsheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    diszpo_pdf_url: Mapped[str | None] = mapped_column(String(500))
    reszvevok: Mapped[str | None] = mapped_column(String(500))
    tulora: Mapped[float | None] = mapped_column(Numeric(6, 2))
    datum: Mapped[date | None] = mapped_column(Date)
    statusz: Mapped[str | None] = mapped_column(
        String(50), comment="PREPARED / PRE_SENT / FULL_READY / FULL_REPLY / FULL_SENT"
    )
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255))

    project: Mapped["Project"] = relationship(back_populates="callsheets")
    employee: Mapped["Employee"] = relationship(back_populates="callsheets")
