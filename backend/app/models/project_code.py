from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProjectCode(TimestampMixin, Base):
    """Pénzügyi egység - 1 Project Code : N Project (forgatás). A pénzügyi mag."""

    __tablename__ = "project_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    projektkod: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))

    datum: Mapped[date | None] = mapped_column(Date)
    esemeny_allapota: Mapped[str | None] = mapped_column(String(50))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    arfolyam: Mapped[float | None] = mapped_column(Numeric(12, 4))
    szerzodes_url: Mapped[str | None] = mapped_column(String(500))
    tig_statusza: Mapped[str | None] = mapped_column(String(50))
    szamla_statusza: Mapped[str | None] = mapped_column(String(50))

    client: Mapped["Client"] = relationship(back_populates="project_codes")
    contract: Mapped["Contract"] = relationship(back_populates="project_codes")
    projects: Mapped[list["Project"]] = relationship(back_populates="project_code")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="project_code")
    revenues: Mapped[list["Revenue"]] = relationship(back_populates="project_code")
    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="project_code")

    @property
    def osszes_koltseg(self) -> float:
        """Számított: belsos + alvallalkozok + vagasi koltseg. Lásd FinanceService."""
        return sum(e.brutto or 0 for e in self.expenses)

    @property
    def becsult_profit(self) -> float:
        bevetel = sum(r.brutto or 0 for r in self.revenues)
        return bevetel - self.osszes_koltseg
