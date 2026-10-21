from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Campaign(TimestampMixin, Base):
    """Kampány - önálló entitás, nem kötve a Project Code maghoz."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    kampany_statusza: Mapped[str | None] = mapped_column(String(50))
    hatarido: Mapped[date | None] = mapped_column(Date)
    intervalluma: Mapped[str | None] = mapped_column(String(120))
    kesz: Mapped[bool] = mapped_column(Boolean, default=False)

    # a 'Kampányok' Notion tábla maradék mezői
    forgatas_utomunka: Mapped[str | None] = mapped_column(String(50), comment="Forgatás/utómunka")
    forgatas: Mapped[bool | None] = mapped_column(Boolean, comment="Forgatás?")
    kreativ_team_database_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Kreatív team database")
    van_utomunka: Mapped[bool | None] = mapped_column(Boolean, comment="Utómunka?")
    kampany_felelose_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Kampány felelőse")
    leiras: Mapped[str | None] = mapped_column(Text, comment="Leírás")
    utomunka_szoveg: Mapped[str | None] = mapped_column(String(255), comment="Utómunka")
    forgatasok_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Forgatások")

    felelos_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))

    felelos: Mapped["Employee"] = relationship(back_populates="campaigns")
    client: Mapped["Client"] = relationship(back_populates="campaigns")
    projects: Mapped[list["Project"]] = relationship(back_populates="campaign")
    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="campaign")
