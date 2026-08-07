"""Ki számláz egy adott projekten egy adott stábtag munkájáért.

Alapesetben mindenki a saját nevében számláz - ilyenkor NINCS sor ebben a
táblában. Ez a tábla csak az ELTÉRÉST rögzíti:

- "Balla Berci munkáját ezen a projekten Ladányi Máté számlázza"
  -> szamlazo_employee_id = Ladányi
- "Ezt az embert a XY Kft. küldte, a cég számláz érte"
  -> szamlazo_vallalkozas_id = XY Kft.

Miért a (projekt, ember) páron és nem az emberen? Mert a felhasználó szerint
ugyanaz az ember "ma innen számláz, holnap saját névről, utána egy harmadik
helyről" - egy emberre akasztott cég-mutató hazudna. A vállalkozáshoz tartozás
(models/vallalkozas.py VallalkozasTag) ezért csak előtöltési JAVASLAT, az
igazság itt van.

Fontos, hogy a lefedett ember (Berci) STÁBTAG marad a projekten: kap diszpót,
rajta van a projekten, a jövedelmezőségben is szerepel. Csak a szerződés és a
TIG megy a másik fél nevére - lásd api/routes/subcontractor_contracts.py
_szamlazo_csoportok, illetve models/performance_certificate.py
PerformanceCertificateTetel.

Miért külön tábla és nem oszlop a project_crew kapcsolótáblán? Mert a stáblista
mentése (PATCH crew_employee_ids) a teljes listát cseréli - egy társított
oszlopot minden egyes stáb-módosítás kitörölne. Külön táblában a beállítás
túléli a stáblista szerkesztését."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProjectSzamlazo(TimestampMixin, Base):
    """Egy (projekt, stábtag) páron a számlázó fél felülírása."""

    __tablename__ = "project_szamlazok"
    __table_args__ = (UniqueConstraint("project_id", "employee_id", name="uq_project_szamlazo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: A LEFEDETT ember - aki a munkát végezte, de nem ő számláz érte.
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: A számlázó fél: pontosan az egyik van kitöltve (lásd szamlazo_kulcs).
    szamlazo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    szamlazo_vallalkozas_id: Mapped[int | None] = mapped_column(ForeignKey("vallalkozasok.id", ondelete="CASCADE"))

    megjegyzes: Mapped[str | None] = mapped_column(String(255))

    project: Mapped["Project"] = relationship(back_populates="szamlazok")
    employee: Mapped["Employee"] = relationship(foreign_keys=[employee_id])
    szamlazo_employee: Mapped["Employee | None"] = relationship(foreign_keys=[szamlazo_employee_id])
    szamlazo_vallalkozas: Mapped["Vallalkozas | None"] = relationship()
