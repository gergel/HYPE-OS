from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class InternalPerformanceCertificate(TimestampMixin, Base):
    """Belsős TIG - a PerformanceCertificate (Külsős TIG) párja belsős
    (payroll-on lévő, nem vállalkozói jogviszonyú) munkatársakhoz. Egyszerűbb
    életciklus, mint a külsősöknél: nincs eseti/keretszerződés-előfeltétel
    (belsősöknek nem kell alvállalkozói szerződés), és nincs Google Docs
    sablon-generálás/email-küldés lépés sem - a folyamat csak annyi, hogy
    admin rögzíti az összeget, feltölti a számlát, majd kifizetettként
    jelöli, ami (a Külsős TIG-hez hasonlóan) létrehoz egy Expense sort a
    projekt project_code_id-jához kötve (lásd api/routes/
    internal_performance_certificates.py)."""

    __tablename__ = "internal_performance_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)

    allapot: Mapped[str | None] = mapped_column(String(50), comment="Belsős TIG állapot")
    megjegyzes: Mapped[str | None] = mapped_column(String(500))
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)
    teljesites_kezdete: Mapped[date | None] = mapped_column(Date)
    teljesites_vege: Mapped[date | None] = mapped_column(Date)

    szamla_url: Mapped[str | None] = mapped_column(String(500), comment="Feltöltött számla fájl URL-je")
    szamla_storage_key: Mapped[str | None] = mapped_column(String(500))
    szamla_kifizetve: Mapped[bool] = mapped_column(Boolean, default=False)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    project: Mapped["Project"] = relationship(back_populates="internal_performance_certificates")
    employee: Mapped["Employee"] = relationship(back_populates="internal_performance_certificates")
