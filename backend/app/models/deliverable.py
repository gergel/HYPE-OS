from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Deliverable(TimestampMixin, Base):
    """Vágandó anyag - utómunka egység, Project Code-hoz és Project-hez is kötve."""

    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_neve: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    vago_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    allapot: Mapped[str | None] = mapped_column(String(50))
    hatarido: Mapped[date | None] = mapped_column(Date)
    koltseg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    kesz_anyag_url: Mapped[str | None] = mapped_column(String(500))
    nyersanyag_url: Mapped[str | None] = mapped_column(String(500))
    anyag_kikuldve: Mapped[bool] = mapped_column(Boolean, default=False)

    # az 'Utómunka' Notion tábla maradék mezői, egyenként (lásd scripts/dump_extra_keys.py)
    tobb_vinyo: Mapped[bool | None] = mapped_column(Boolean, comment="Több vinyó")
    timesheet_status: Mapped[str | None] = mapped_column(String(100))
    stop_timer: Mapped[bool | None] = mapped_column(Boolean)
    completed_notion: Mapped[bool | None] = mapped_column(Boolean, comment="Completed")
    time_minutes: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="Time (minutes)")
    jovairva: Mapped[bool | None] = mapped_column(Boolean, comment="jóváírva")
    total_time: Mapped[str | None] = mapped_column(String(50), comment="Total time")
    anyag_zapierbe: Mapped[bool | None] = mapped_column(Boolean)
    updated_at_notion: Mapped[datetime | None] = mapped_column(DateTime, comment="Last edited time")
    vinyok: Mapped[dict | list | None] = mapped_column(JSON, comment="Vinyók")
    projektkod_szoveg: Mapped[str | None] = mapped_column(String(50), comment="Projektkód")
    completed_time: Mapped[date | None] = mapped_column(Date)
    vagas_leiras: Mapped[str | None] = mapped_column(Text, comment="Vágás leírás")
    aki_felvezette_az_utomunkat_notion_ids: Mapped[dict | list | None] = mapped_column(
        JSON, comment="Aki felvezette az utómunkát"
    )
    jovairando_pont: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="jóváírandó pont")
    timesheet_public_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Timesheet Public")
    timesheet_private_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Timesheet Private")
    forgatas_datuma_notion: Mapped[str | None] = mapped_column(String(100), comment="Forgatás dátuma")
    esemeny_neve: Mapped[str | None] = mapped_column(String(255), comment="Esemény neve")
    aki_ellenorzesbe_tette_notion_ids: Mapped[dict | list | None] = mapped_column(
        JSON, comment="Aki ellenőrzésbe tette 1"
    )
    megrendeloi_email_cimek: Mapped[str | None] = mapped_column(Text, comment="Megrendelői email címek")
    email_megnevezes: Mapped[str | None] = mapped_column(String(255))
    megrendeloi_kontaktok_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Megrendelői kontaktok")
    archivalas: Mapped[str | None] = mapped_column(String(50), comment="Archiválás")
    label: Mapped[str | None] = mapped_column(String(100))
    assigned_to_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Assigned To")
    visszajelzessek_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Visszajelzéssek")
    files_vagashoz_urls: Mapped[dict | list | None] = mapped_column(JSON, comment="Files vágáshoz")
    esedekes: Mapped[str | None] = mapped_column(String(120), comment="Esedékes")
    email_forgatas_datum: Mapped[str | None] = mapped_column(String(50))
    xp: Mapped[str | None] = mapped_column(String(20), comment="XP")
    pontozas: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="Pontozás")
    egyeb_megjegyzes: Mapped[str | None] = mapped_column(Text, comment="Egyéb megjegyzés")
    nyersanyag_felhasznalhatosaga: Mapped[float | None] = mapped_column(Numeric(4, 2))
    technikai_helyesseg: Mapped[float | None] = mapped_column(Numeric(4, 2))
    kreativ_es_kepi_vilag: Mapped[float | None] = mapped_column(Numeric(4, 2), comment="Kreatív és képi világ")

    project_code: Mapped["ProjectCode"] = relationship(back_populates="deliverables")
    project: Mapped["Project"] = relationship(back_populates="deliverables")
    vago: Mapped["Employee"] = relationship(back_populates="deliverables")
    campaign: Mapped["Campaign"] = relationship(back_populates="deliverables")

    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="deliverable")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="deliverable")
