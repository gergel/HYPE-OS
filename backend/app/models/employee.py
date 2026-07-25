from datetime import date
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class EmployeeType(StrEnum):
    """Üzleti típus (a korábbi Vágók / Külsős / Belsős / Kreatív team / Hype Stáb táblák egyesítve)."""

    BELSOS = "belsos"
    KULSOS = "kulsos"
    VAGO = "vago"
    KREATIV = "kreativ"
    STAB = "stab"


class SystemRole(StrEnum):
    """Auth/jogosultsági szerepkör - független az üzleti tipus mezőtől."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VAGO = "vago"
    UGYFEL = "ugyfel"


class Employee(TimestampMixin, Base):
    """Crew tag - belsős, külsős, vágó, kreatív vagy stáb (Employee entitás)."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tipus: Mapped[EmployeeType] = mapped_column(
        Enum(EmployeeType, name="employee_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # SZÁNDÉKOSAN nem egyedi: a valóságban több embernek is lehet ugyanaz a
    # címe (közös cég-postafiók, vagy egy stábtag a főnöke címét adja meg),
    # és a korábbi unique megkötés miatt ilyenkor egyszerűen nem lehetett
    # felvenni a második embert. Az index megmarad, mert a bejelentkezés e
    # szerint keres (lásd api/routes/auth.py - ott a jelszó dönti el, melyik
    # azonos című fiókról van szó).
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    telefon: Mapped[str | None] = mapped_column(String(50))
    jogositvany: Mapped[str | None] = mapped_column(String(255))

    ertekeles: Mapped[float | None] = mapped_column()
    elso_munkanap: Mapped[date | None] = mapped_column(Date)
    utolso_munkanap: Mapped[date | None] = mapped_column(Date)

    # --- Auth ---
    role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="system_role", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SystemRole.OPERATOR,
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- a 'Külsős és belsős' Notion tábla maradék mezői ---
    technikai_ismeret: Mapped[str | None] = mapped_column(Text, comment="TECHNIKAI ISMERET")
    vallalkozas_kepviselo: Mapped[str | None] = mapped_column(String(255), comment="Vállalkozás képviselő")
    leltar_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="🎥 Leltár (relation)")
    hany_visszajelzese_van_notion: Mapped[dict | None] = mapped_column(JSON, comment="Hány visszajelzése van")
    first_name: Mapped[str | None] = mapped_column(String(120), comment="First name")
    last_name: Mapped[str | None] = mapped_column(String(120), comment="Last name")
    munkanapok_notion: Mapped[dict | None] = mapped_column(JSON, comment="Munkanapok")
    linkedin_profile: Mapped[str | None] = mapped_column(String(500), comment="LinkedIn Profile")
    twitter_profile: Mapped[str | None] = mapped_column(String(500), comment="Twitter Profile")
    facebook_profile: Mapped[str | None] = mapped_column(String(500), comment="Facebook Profile")
    photo_url: Mapped[str | None] = mapped_column(String(500), comment="Photo")
    kulsos_tig_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Külsős TIG (relation)")
    belsos_tig_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Belsős TIG (relation)")
    orabler_notion: Mapped[str | None] = mapped_column(String(100), comment="Órabér (formula, pillanatkép)")
    napidij_notion: Mapped[str | None] = mapped_column(String(100), comment="Napidíj (formula, pillanatkép)")
    extra_kiadas_megnevezes: Mapped[str | None] = mapped_column(String(255), comment="Extra kiadás megnevezés")
    extra_kiadas_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Extra kiadás összeg")
    extra_kiadas_datuma: Mapped[date | None] = mapped_column(Date, comment="Extra kiadás dátuma")
    belsos_havi_tig: Mapped[bool | None] = mapped_column(Boolean, comment="Belsős Havi TIG")
    source: Mapped[str | None] = mapped_column(String(100), comment="Source")
    events_involved_count_notion: Mapped[dict | None] = mapped_column(JSON, comment="Events involved count (Σ)")
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó összeg")
    linked_events_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Linked Events (relation)")
    leltar_hiany_20240415_notion: Mapped[dict | None] = mapped_column(JSON, comment="2024.04.15. leltár hiány")
    legutolso_napi_dij_megegyezes: Mapped[str | None] = mapped_column(
        String(255), comment="LEGUTOLSÓ NAPI DÍJ MEGEGYEZÉS"
    )
    milyen_suru_hivjuk: Mapped[str | None] = mapped_column(String(255), comment="MILYEN SŰRŰN HÍVJUK")
    megbizas_targya: Mapped[str | None] = mapped_column(String(255), comment="Megbízás tárgya")
    szallito_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Szállító (relation)")
    keltezes_datuma: Mapped[date | None] = mapped_column(Date, comment="Keltezés dátuma")
    archive_technika_elhagyas_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Archive technika elhagyás (relation)"
    )
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100), comment="Nyilvántartási szám:")
    vallakozas_szekhely: Mapped[str | None] = mapped_column(String(500), comment="Vállakozás székhely")
    van_e_email_cime_notion: Mapped[dict | None] = mapped_column(JSON, comment="van e email címe")
    vallakozas_neve: Mapped[str | None] = mapped_column(String(255), comment="Vállakozás neve")
    phone_2: Mapped[str | None] = mapped_column(String(50), comment="Phone 2")
    megjegyzes: Mapped[str | None] = mapped_column(Text, comment="MEGJEGYZÉS")
    honnan_ismerjuk: Mapped[str | None] = mapped_column(Text, comment="HONNAN ISMERJÜK")
    birthday: Mapped[date | None] = mapped_column(Date, comment="Birthday")
    kiadas_projektkodja_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Kiadás projektkódja (relation)")
    formula_2_notion: Mapped[dict | None] = mapped_column(JSON, comment="Formula 2")
    main_database_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="📅 Main Database (relation)")
    vallalkozas_adoszama: Mapped[str | None] = mapped_column(String(50), comment="Vállalkozás adószáma")
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean, comment="Plusz ÁFA")

    rates: Mapped[list["Rate"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    documents: Mapped[list["EmployeeDocument"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="employee")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="employee")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="employee")
    performance_certificates: Mapped[list["PerformanceCertificate"]] = relationship(back_populates="employee")
    internal_performance_certificates: Mapped[list["InternalPerformanceCertificate"]] = relationship(back_populates="employee")
    callsheets: Mapped[list["Callsheet"]] = relationship(back_populates="employee")
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="vago", foreign_keys="Deliverable.vago_employee_id"
    )
    feedbacks: Mapped[list["Feedback"]] = relationship(
        back_populates="forgatta", foreign_keys="Feedback.forgatta_employee_id"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="felelos")
    tasks: Mapped[list["Task"]] = relationship(
        secondary="task_employees", back_populates="felelosok"
    )
    projects: Mapped[list["Project"]] = relationship(
        secondary="project_crew", back_populates="crew"
    )
