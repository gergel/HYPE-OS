from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, String, Table, Text
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
    """Feladat - TEENDŐK + Archive feladatok egyesítve.

    Az Ági to do list és a HYPE TO-DO LIST KORÁBBAN ide tartozott (nyers JSON
    maradék-mezőkkel), de mostantól saját, típusos táblájuk van (lásd
    models/agi_todo.py, models/hype_todo.py) - a felhasználó kifejezett
    kérésére. A `*_notion` maradék mezők itt csak a TEENDŐK/Archive
    feladatok két forrás miatt maradtak."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    feladat: Mapped[str] = mapped_column(String(500), nullable=False)
    allapot: Mapped[str | None] = mapped_column(String(50))
    hatarido: Mapped[date | None] = mapped_column(Date)
    kategoria: Mapped[str | None] = mapped_column(String(100))
    #: Melyik projekthez tartozik a feladat. Az automatikusan generált
    #: papírozás-feladatoknál ez adja az idempotenciát: projektenként legfeljebb
    #: egy ilyen születhet (lásd services/papirozas_feladatok.py).
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    leiras: Mapped[str | None] = mapped_column(String(2000))

    # a TEENDŐK/Ági to do list/HYPE TO-DO LIST/Archive feladatok táblák maradék mezői
    aki_felvezette_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Aki felvezette")
    letrehozas_idopontja: Mapped[datetime | None] = mapped_column(DateTime, comment="Létrehozás időpontja")
    felelos_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Felelős")
    ugyfel: Mapped[str | None] = mapped_column(String(255), comment="Ügyfél")
    ellenorzes_felelos_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Ellenőrzés felelős")
    aki_ellenorizte_keszbe_rakta_notion: Mapped[dict | list | None] = mapped_column(
        JSON, comment="Aki ellenőrizte/készbe rakta"
    )
    kovetkezo_lepes: Mapped[str | None] = mapped_column(Text, comment="Következő lépés")
    csatolni_valo_urls: Mapped[dict | list | None] = mapped_column(JSON, comment="Csatolni való")
    files_media_urls: Mapped[dict | list | None] = mapped_column(JSON, comment="Files & media")

    felelosok: Mapped[list["Employee"]] = relationship(secondary=task_employees, back_populates="tasks")
