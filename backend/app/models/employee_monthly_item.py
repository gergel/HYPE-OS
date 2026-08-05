from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

# A tétel szerepe. Az "alapber" a havi fix rész, minden más "extra" (túlóra,
# benzin, étkezés…). Azért nem egy fix konstans az alapbér a munkatárs
# törzsadatában, mert hónapról hónapra változhat - így minden hónapnak megvan
# a SAJÁT, visszakereshető alapbére.
TETEL_TIPUSOK = ("alapber", "extra")


class EmployeeMonthlyItem(TimestampMixin, Base):
    """Egy belsős munkatárs adott havi juttatás-tétele: az alapbér, és a
    hozzáadódó extrák (túlóra, benzin, étkezés…), tételenként projekthez is
    köthetően.

    Ezek a tételek adják ki a havi Belsős TIG összegét: bármelyik módosítása
    újraszámolja a hónap TIG-jének nettó összegét (lásd
    api/routes/internal_performance_certificates.py _ujraszamol_tig_osszeget),
    így aki a TIG-et készíti, már a kész összeget látja - nem neki kell
    összeadnia a hónap közben felmerült extrákat.

    A már véglegesített (kiküldött/kész/kihagyott) TIG összegét NEM írjuk át:
    egy kiküldött igazolás összege nem változhat utólag."""

    __tablename__ = "employee_monthly_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    ev: Mapped[int] = mapped_column(nullable=False, comment="Év, pl. 2026")
    honap: Mapped[int] = mapped_column(nullable=False, comment="Hónap, 1-12")

    tipus: Mapped[str] = mapped_column(String(20), nullable=False, default="extra", comment="alapber | extra")
    megnevezes: Mapped[str] = mapped_column(String(255), nullable=False)
    osszeg: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Melyik projekthez kapcsolódik az extra (túlóra, kiszállás) - a havi
    # összesítőben így látszik, melyik munka mennyibe került.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    datum: Mapped[date | None] = mapped_column(Date, comment="A tétel napja a hónapon belül (opcionális)")
    megjegyzes: Mapped[str | None] = mapped_column(String(500))

    employee: Mapped["Employee"] = relationship(back_populates="monthly_items")
    project: Mapped["Project | None"] = relationship()

    __table_args__ = (Index("ix_employee_monthly_items_employee_honap", "employee_id", "ev", "honap"),)
