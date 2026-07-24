from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class InternalPerformanceCertificate(TimestampMixin, Base):
    """Belsős TIG - a PerformanceCertificate (Külsős TIG) párja belsős
    (payroll-on lévő, nem vállalkozói jogviszonyú) munkatársakhoz, de MÁS
    ciklusú: belsősöknek sosem kell projektenként TIG-et készíteni, hanem
    havonta pontosan egyet (lásd api/routes/internal_performance_certificates.py
    - egy admin oldal listázza az adott hónap összes belsős munkatársát,
    alapértelmezetten a folyó hónapra). A (employee_id, ev, honap) hármas
    egyedi - egy embernek egy hónapban csak egy TIG-je lehet.

    Egyszerűbb életciklus, mint a külsősöknél: nincs eseti/keretszerződés-
    előfeltétel, és nincs Google Docs sablon-generálás/email-küldés lépés
    sem - a folyamat csak annyi, hogy admin rögzíti az összeget, feltölti a
    számlát, majd kifizetettként jelöli, ami (a Külsős TIG-hez hasonlóan)
    létrehoz egy Expense sort - de projekthez/projektkódhoz NEM köthető,
    hiszen a belsős TIG nem egyetlen projekt teljesítését igazolja."""

    __tablename__ = "internal_performance_certificates"
    __table_args__ = (UniqueConstraint("employee_id", "ev", "honap", name="uq_internal_tig_employee_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    ev: Mapped[int] = mapped_column(nullable=False, comment="Év, pl. 2026")
    honap: Mapped[int] = mapped_column(nullable=False, comment="Hónap, 1-12")

    allapot: Mapped[str | None] = mapped_column(String(50), comment="Belsős TIG állapot")
    megjegyzes: Mapped[str | None] = mapped_column(String(500))
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)

    szamla_url: Mapped[str | None] = mapped_column(String(500), comment="Feltöltött számla fájl URL-je")
    szamla_storage_key: Mapped[str | None] = mapped_column(String(500))
    szamla_kifizetve: Mapped[bool] = mapped_column(Boolean, default=False)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    employee: Mapped["Employee"] = relationship(back_populates="internal_performance_certificates")
