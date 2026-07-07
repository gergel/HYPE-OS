from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ContractType(StrEnum):
    """Keretszerződés (ügyféllel) vagy alvállalkozói/eseti (crew-val)."""

    KERETSZERZODES = "kereto"
    ALVALLALKOZOI = "alvallalkozoi"


class Contract(TimestampMixin, Base):
    """Szerződés - Keretszerződés + Alvállalkozó keretszerződés egyesítve, tipus mezővel."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipus: Mapped[ContractType] = mapped_column(
        Enum(ContractType, name="contract_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    # Csak az ALVALLALKOZOI tipusú, egy adott projekthez tartozó eseti
    # szerződéseknél van kitöltve (lásd services/subcontractor_contracts.py) -
    # NULL esetén a Contract egy álló "keretszerződés" (a megbízottnak bármelyik
    # jövőbeli projektjére érvényes, nincs egyetlen projekthez sem kötve).
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))

    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(255))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    szerzodes_allapota: Mapped[str | None] = mapped_column(String(50))
    szerzodes_file_url: Mapped[str | None] = mapped_column(String(500))
    keltezes: Mapped[date | None] = mapped_column(Date)
    alairva: Mapped[bool] = mapped_column(Boolean, default=False)

    # Eseti (projektenkénti) alvállalkozói szerződés mezői - a csatolt
    # "kulsos-eseti-szerzodes" program Notion-mezőinek megfelelői.
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó összeg")
    teljesites_kezdete: Mapped[date | None] = mapped_column(Date, comment="Teljesítés kezdete")
    teljesites_vege: Mapped[date | None] = mapped_column(Date, comment="Teljesítés vége")
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean, comment="Plusz ÁFA")

    # a 'Keretszerződés' / 'Alvállakozó keretszerződés' Notion táblák maradék mezői
    letrehozta_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Created by")
    vallalkozas_kepviseloje: Mapped[str | None] = mapped_column(String(255), comment="Vállalkozás képviselője")
    created_at_notion: Mapped[datetime | None] = mapped_column(DateTime, comment="Created time")
    keretszerzodes_kuld: Mapped[bool | None] = mapped_column(Boolean, comment="Keretszerződés küld")
    email: Mapped[str | None] = mapped_column(String(255))
    szemely_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Személy")
    nev: Mapped[str | None] = mapped_column(String(255), comment="Name")
    kulsos_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Külsős")
    vallalkozas_nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100))
    szerzodes_megjegyzes: Mapped[str | None] = mapped_column(Text)

    client: Mapped["Client"] = relationship(back_populates="contracts")
    employee: Mapped["Employee"] = relationship(back_populates="contracts")
    project: Mapped["Project | None"] = relationship(back_populates="contracts", foreign_keys=[project_id])
    project_codes: Mapped[list["ProjectCode"]] = relationship(back_populates="contract")
