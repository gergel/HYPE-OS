from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Timesheet(TimestampMixin, Base):
    """Ledolgozott idő - vágási óraköltség számításhoz (Rate x óra)."""

    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    deliverable_id: Mapped[int | None] = mapped_column(ForeignKey("deliverables.id"))

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    koltseg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    statusz: Mapped[str | None] = mapped_column(String(50))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Melyik Notion-táblából jött a sor: "public" vagy "private". A HYPE
    # Notionban ugyanaz a mérés MINDKÉT táblában szerepelhet (a két táblát egy
    # szinkron-worker tartotta párban) - enélkül ugyanaz a munkaidő kétszer
    # számítana bele az utómunka összesítésébe. Üres a rendszerben indított
    # (nem importált) méréseknél.
    notion_forras: Mapped[str | None] = mapped_column(String(20))

    # a munkaidő-elszámoló táblák maradék mezői (lásd scripts/dump_extra_keys.py)
    person_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Person")
    fut: Mapped[bool | None] = mapped_column(Boolean)
    orabere: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Órabér")
    timesheet_status: Mapped[str | None] = mapped_column(String(100))
    nev: Mapped[str | None] = mapped_column(String(255), comment="Name")
    time_xp: Mapped[str | None] = mapped_column(String(20), comment="Time XP")
    time_szoveg: Mapped[str | None] = mapped_column(String(50), comment="Time")
    time_minutes: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="Time (minutes)")
    xp_pontozas: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="XP pontozás")
    vagok_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Vágók")
    mai_percek: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="Mai percek")
    percek_2025_majus: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="2025 május percek")
    mai_xp: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="Mai xp")
    kezdes_ma: Mapped[bool | None] = mapped_column(Boolean, comment="kezdés ma")
    akkori_orabere: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Akkori órabér")
    timesheet_public_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Timesheet Public")
    percek_lista: Mapped[dict | list | None] = mapped_column(JSON, comment="percek")

    employee: Mapped["Employee"] = relationship(back_populates="timesheets")
    deliverable: Mapped["Deliverable"] = relationship(back_populates="timesheets")

    @property
    def idotartam_perc(self) -> int | None:
        if self.start_date is None or self.end_date is None:
            return None
        return int((self.end_date - self.start_date).total_seconds() // 60)
