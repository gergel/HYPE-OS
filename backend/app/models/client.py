from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Client(TimestampMixin, Base):
    """Ügyfél (cég) - a Project Code, Contract és Campaign tulajdonosa."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    adoszam: Mapped[str | None] = mapped_column(String(50))
    szekhely: Mapped[str | None] = mapped_column(String(255))
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100))
    kepviselo: Mapped[str | None] = mapped_column(String(255))

    contacts: Mapped[list["Contact"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    project_codes: Mapped[list["ProjectCode"]] = relationship(back_populates="client")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="client")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="client")


class Contact(TimestampMixin, Base):
    """Kapcsolattartó egy Client oldalán."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))

    # a 'Megrendelői kontaktok' Notion tábla maradék mezői
    keresztnev_notion: Mapped[str | None] = mapped_column(String(120), comment="Keresztnév (formula)")
    vezeteknev_notion: Mapped[str | None] = mapped_column(String(120), comment="Vezeték név (formula)")
    torolt_anyagok_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Törölt anyagok (relation)")
    kreativ_team_database_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Kreatív team database (relation)"
    )

    client: Mapped["Client"] = relationship(back_populates="contacts")
