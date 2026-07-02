from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Expense(TimestampMixin, Base):
    """Kiadás - Kiadások + Projekt kiadások + Belsős extra kiadások egyesítve."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    megnevezes: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    tipus: Mapped[str | None] = mapped_column(String(50), comment="belsos / kulsos / extra")
    netto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    kifizetes_modja: Mapped[str | None] = mapped_column(String(50))
    fizetes_hatarideje: Mapped[date | None] = mapped_column(Date)
    kesz: Mapped[bool] = mapped_column(Boolean, default=False)

    project_code: Mapped["ProjectCode"] = relationship(back_populates="expenses")
    employee: Mapped["Employee"] = relationship(back_populates="expenses")
    kp_forgalmak: Mapped[list["KpForgalom"]] = relationship(back_populates="expense")


class Revenue(TimestampMixin, Base):
    """Bevétel - egy Project Code-hoz kötve."""

    __tablename__ = "revenues"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False)

    bevetel_formaja: Mapped[str | None] = mapped_column(String(50))
    netto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    fizetes_hatarideje: Mapped[date | None] = mapped_column(Date)
    fizetes_datuma: Mapped[date | None] = mapped_column(Date)

    project_code: Mapped["ProjectCode"] = relationship(back_populates="revenues")
    payments: Mapped[list["Payment"]] = relationship(back_populates="revenue")


class KpForgalom(TimestampMixin, Base):
    """KP forgalom - önálló entitás, kapcsolódik az Expense-hez, de nem olvad bele."""

    __tablename__ = "kp_forgalmak"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    forgalom: Mapped[str | None] = mapped_column(String(50), comment="bevetel / kiadas")
    osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    legalis: Mapped[str | None] = mapped_column(String(50))
    kiadas_datuma: Mapped[date | None] = mapped_column(Date)

    expense: Mapped["Expense"] = relationship(back_populates="kp_forgalmak")

    @property
    def forintban(self) -> float | None:
        """Az összeg forintra váltva - az árfolyam-logikát a FinanceService számolja."""
        return self.osszeg if self.penznem == "HUF" else None
