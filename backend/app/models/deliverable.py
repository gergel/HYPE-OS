from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

deliverable_contacts = Table(
    "deliverable_contacts",
    Base.metadata,
    Column("deliverable_id", ForeignKey("deliverables.id"), primary_key=True),
    Column("contact_id", ForeignKey("contacts.id"), primary_key=True),
)


class Deliverable(TimestampMixin, Base):
    """Vágandó anyag - utómunka egység, Project Code-hoz és Project-hez is kötve."""

    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_neve: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    vago_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    # Ki hozta létre az utómunkát (a fiókja, amivel az "Utómunka" gombot
    # megnyomta - lásd services/project_actions.create_utomunka), és kire van
    # kiosztva a munka (csak olyan munkatárs válaszható, akinek van
    # bejelentkezési hozzáférése az /utomunka oldalhoz - lásd
    # routes/postproduction.py list_assignable_employees).
    aki_felvezette_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    assigned_to_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

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
    # A nyers Notion relation-lista (csak névsztring) - a valódi kapcsolatot
    # az aki_felvezette_employee_id FK adja, ez csak import-örökség/backup.
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
    # Formula-mező: a megrendeloi_kontaktok (lásd lent) e-mail címeinek
    # vesszővel elválasztott felsorolása - lásd services/deliverable_actions,
    # sosem szerkeszthető közvetlenül, mindig újraszámolódik a kontaktokból.
    megrendeloi_email_cimek: Mapped[str | None] = mapped_column(Text, comment="Megrendelői email címek")
    email_megnevezes: Mapped[str | None] = mapped_column(String(255))
    # A nyers Notion relation-lista - a valódi kapcsolatot a megrendeloi_kontaktok
    # m2m reláció adja, ez csak import-örökség/backup.
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
    vago: Mapped["Employee"] = relationship(back_populates="deliverables", foreign_keys=[vago_employee_id])
    felvezeto: Mapped["Employee"] = relationship(foreign_keys=[aki_felvezette_employee_id])
    assigned_to: Mapped["Employee"] = relationship(foreign_keys=[assigned_to_employee_id])
    campaign: Mapped["Campaign"] = relationship(back_populates="deliverables")
    megrendeloi_kontaktok: Mapped[list["Contact"]] = relationship(secondary=deliverable_contacts)

    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="deliverable")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="deliverable")
    comments: Mapped[list["DeliverableComment"]] = relationship(back_populates="deliverable", order_by="DeliverableComment.created_at")
    portal: Mapped["Portal | None"] = relationship(back_populates="deliverable", uselist=False)

    @property
    def portal_id(self) -> int | None:
        """A DeliverableRead séma erre hivatkozik, hogy a frontend eldönthesse:
        van-e már Média Portál ehhez a vágandó anyaghoz (lásd
        routes/portal_admin.py create_portal_from_deliverable)."""
        return self.portal.id if self.portal else None
