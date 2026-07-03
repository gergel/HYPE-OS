from datetime import date
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class EmployeeType(StrEnum):
    """Üzleti típus (a korábbi Vágók / Külsős / Belsős / Kreatív team / Hype Stáb táblák egyesítve)."""

    BELSOS = "belsos"
    KULSOS = "kulsos"
    VAGO = "vago"
    KREATIV = "kreativ"
    STAB = "stab"


class SystemRole(StrEnum):
    """Auth/jogosultsági szerepkör - független az üzleti tipus mezőtől."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VAGO = "vago"
    UGYFEL = "ugyfel"


class Employee(TimestampMixin, Base):
    """Crew tag - belsős, külsős, vágó, kreatív vagy stáb (Employee entitás)."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tipus: Mapped[EmployeeType] = mapped_column(
        Enum(EmployeeType, name="employee_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    telefon: Mapped[str | None] = mapped_column(String(50))
    jogositvany: Mapped[str | None] = mapped_column(String(255))

    munkaszerzodes_url: Mapped[str | None] = mapped_column(String(500))
    ertekeles: Mapped[float | None] = mapped_column()
    elso_munkanap: Mapped[date | None] = mapped_column(Date)
    utolso_munkanap: Mapped[date | None] = mapped_column(Date)

    # --- Auth ---
    role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="system_role", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SystemRole.OPERATOR,
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    extra: Mapped[dict | None] = mapped_column(JSON)

    rates: Mapped[list["Rate"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="employee")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="employee")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="employee")
    callsheets: Mapped[list["Callsheet"]] = relationship(back_populates="employee")
    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="vago")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="forgatta")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="felelos")
    tasks: Mapped[list["Task"]] = relationship(
        secondary="task_employees", back_populates="felelosok"
    )
    projects: Mapped[list["Project"]] = relationship(
        secondary="project_crew", back_populates="crew"
    )
