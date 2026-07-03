from datetime import date

from sqlalchemy import JSON, Boolean, Column, Date, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

task_employees = Table(
    "task_employees",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id"), primary_key=True),
    Column("employee_id", ForeignKey("employees.id"), primary_key=True),
)


class Task(TimestampMixin, Base):
    """Feladat - TEENDŐK + Ági to do list + HYPE TO-DO LIST + Archive feladatok egyesítve."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    feladat: Mapped[str] = mapped_column(String(500), nullable=False)
    allapot: Mapped[str | None] = mapped_column(String(50))
    hatarido: Mapped[date | None] = mapped_column(Date)
    kategoria: Mapped[str | None] = mapped_column(String(100))
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    leiras: Mapped[str | None] = mapped_column(String(2000))
    extra: Mapped[dict | None] = mapped_column(JSON)

    felelosok: Mapped[list["Employee"]] = relationship(secondary=task_employees, back_populates="tasks")
