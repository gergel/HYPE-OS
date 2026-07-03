from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Deliverable(TimestampMixin, Base):
    """Vágandó anyag - utómunka egység, Project Code-hoz és Project-hez is kötve."""

    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_neve: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    vago_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    allapot: Mapped[str | None] = mapped_column(String(50))
    hatarido: Mapped[date | None] = mapped_column(Date)
    koltseg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    kesz_anyag_url: Mapped[str | None] = mapped_column(String(500))
    nyersanyag_url: Mapped[str | None] = mapped_column(String(500))
    anyag_kikuldve: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict | None] = mapped_column(JSON)

    project_code: Mapped["ProjectCode"] = relationship(back_populates="deliverables")
    project: Mapped["Project"] = relationship(back_populates="deliverables")
    vago: Mapped["Employee"] = relationship(back_populates="deliverables")
    campaign: Mapped["Campaign"] = relationship(back_populates="deliverables")

    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="deliverable")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="deliverable")
