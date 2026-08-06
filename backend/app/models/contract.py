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
    # Álló KERETSZERZŐDÉS-e ez a sor, vagy egy ESETI megbízási szerződés?
    #
    # A projekt nélküli (project_id IS NULL) alvállalkozói sorok kétfélék:
    # - a Notion "Alvállakozó keretszerződés (külsős)" táblájából jövők - ezek
    #   a valódi keretszerződések, ezek mentesítenek a projektenkénti eseti
    #   szerződés alól (itt True);
    # - a "Külsős és belsős" tábla emberei mellől jövők (cégadat + a lapjukon
    #   lévő aláírt PDF) - ezek eseti megbízási szerződések, nem keretszerződés
    #   (itt False), lásd notion_import/importers.py.
    keretszerzodes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Eseti (projektenkénti) alvállalkozói szerződés mezői - a csatolt
    # "kulsos-eseti-szerzodes" program Notion-mezőinek megfelelői.
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó összeg")
    # A teljesítés ideje SZABAD SZÖVEG: nem mindig egy naptól-napig tartomány
    # ("2026.05.03.", "május 3-5.", "a projekt teljes időtartama"), és a
    # szerződésben pontosan az kell szerepeljen, amit ide írnak. A régi,
    # dátumpáros bejegyzésekhez a két alatta lévő oszlop marad tartaléknak
    # (lásd routes/subcontractor_contracts.py _teljesites_szovege).
    teljesites_szoveg: Mapped[str | None] = mapped_column(String(255), comment="Teljesítés ideje - szabad szöveg")
    teljesites_kezdete: Mapped[date | None] = mapped_column(Date, comment="Teljesítés kezdete (régi, dátumpáros adat)")
    teljesites_vege: Mapped[date | None] = mapped_column(Date, comment="Teljesítés vége (régi, dátumpáros adat)")
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


def megkotott_keretszerzodes(szerzodes: Contract) -> bool:
    """Valódi, álló keretszerződés-e ez a sor?

    Keretszerződése annak van, aki a Notion "Alvállakozó keretszerződés
    (külsős)" táblájában szerepel - ezt a `keretszerzodes` jelölő hordozza,
    amit az import és a kézi felvétel állít be (lásd
    notion_import/importers.py import_contracts, illetve
    api/routes/contracts.py create_keretszerzodes).

    A többi projekt nélküli alvállalkozói sor ESETI megbízási szerződés: ezek
    a "Külsős és belsős" tábla emberei mellől jönnek (cégadat + a saját
    lapjukon lévő aláírt PDF). Ha ezeket keretszerződésnek vennénk, az
    utókövetés elromlana - mindenkiről azt hinné a rendszer, hogy van álló
    szerződése, és senkinek nem kérné az eseti szerződést."""
    if szerzodes.project_id is not None or szerzodes.tipus != ContractType.ALVALLALKOZOI:
        return False
    return bool(szerzodes.keretszerzodes)


def eseti_megbizasi_szerzodes(szerzodes: Contract) -> bool:
    """Eseti megbízási szerződés-e? Minden alvállalkozói szerződés, ami nem
    álló keretszerződés - akár egy projekthez kötött (lásd
    services/subcontractor_contracts.py), akár a munkatárs Notion-lapjáról
    jött, projekt nélküli sor."""
    return szerzodes.tipus == ContractType.ALVALLALKOZOI and not megkotott_keretszerzodes(szerzodes)
