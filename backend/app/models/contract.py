from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
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
    # A szerződés másik oldala lehet egy CÉG is, nem csak egy ember: a
    # forgatásra embereket küldő vállalkozással kötünk keretszerződést, és az
    # fedi az összes tőle jövő embert (lásd models/vallalkozas.py). Ilyenkor az
    # employee_id üres. Eseti szerződésnél ugyanígy: ha a projekten a számlázó
    # fél egy cég, a szerződés a cég nevére szól.
    vallalkozas_id: Mapped[int | None] = mapped_column(ForeignKey("vallalkozasok.id"))
    # Csak az ALVALLALKOZOI tipusú, egy adott projekthez tartozó eseti
    # szerződéseknél van kitöltve (lásd services/subcontractor_contracts.py) -
    # NULL esetén a Contract vagy egy álló "keretszerződés" (a megbízottnak
    # bármelyik jövőbeli projektjére érvényes, nincs egyetlen projekthez sem
    # kötve), vagy - ha a project_code_id ki van töltve - egy FORGATÁS NÉLKÜLI,
    # tisztán projektkódhoz kötött eseti szerződés (lásd project_code_id).
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    # Csak akkor van kitöltve, ha ALVALLALKOZOI eseti szerződés úgy készül,
    # hogy a projektkódhoz NINCS forgatás (tisztán ügynökségi feladat, pl.
    # tanácsadás) - a projekt_id ilyenkor üres, mert nincs is Project sor,
    # amihez kötni lehetne. A project_id és a project_code_id EGYSZERRE soha
    # nem tölthető ki (lásd api/routes/subcontractor_contracts.py "projektkód-
    # szintű ág" - _get_or_create_draft_projektkodon).
    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))

    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(255))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    szerzodes_allapota: Mapped[str | None] = mapped_column(String(50))
    szerzodes_file_url: Mapped[str | None] = mapped_column(String(500))
    # Lásd PerformanceCertificate.file_storage_key: csak a MI tárhelyünkre
    # feltöltött saját szerződésnél van kitöltve, a generált, Drive-on maradó
    # dokumentumnál üres.
    szerzodes_file_storage_key: Mapped[str | None] = mapped_column(String(500))
    #: A megbízott által ALÁÍRVA visszaküldött példány - külön a fentitől, mert
    #: az a MI dokumentumunk (generált vagy feltöltött), ez pedig a visszaérkező
    #: papír. Amíg ez nincs meg, a projekt "aláírt szerződésre vár" az
    #: utókövetésben (lásd routes/utokovetes_admin.py).
    alairt_file_url: Mapped[str | None] = mapped_column(String(500))
    alairt_file_storage_key: Mapped[str | None] = mapped_column(String(500))
    keltezes: Mapped[date | None] = mapped_column(Date)
    #: Visszaérkezett-e aláírva. A feltöltés állítja be, de kézzel is
    #: jelölhető: van, hogy a papír máshol landol, és csak a tény kell.
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
    #: Él-e most a keretszerződés? Ez a kézi kapcsoló: ha ki van kapcsolva, az
    #: érvényességi időszakoktól függetlenül eseti szerződést kérünk.
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
    #: MIÉRT hagytuk ki, vagy miért nem itt készült a papír. Külön a fenti,
    #: Notionból örökölt általános megjegyzéstől: ez kizárólag a lezárás
    #: indoklása, és a kihagyáskor kötelező megadni - fél év múlva senki nem
    #: fogja fejből tudni, miért maradt el egy szerződés.
    kihagyas_oka: Mapped[str | None] = mapped_column(Text)

    #: Mettől meddig élt a keretszerződés - több, egymást követő időszak is
    #: lehet (lásd ContractPeriod).
    idoszakok: Mapped[list["ContractPeriod"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="ContractPeriod.kezdet"
    )

    #: Mire szól az ESETI szerződés: kinek a munkájára, melyik projekteken
    #: (lásd ContractTetel). Keretszerződésnél üres - az nincs projekthez kötve.
    tetelek: Mapped[list["ContractTetel"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="ContractTetel.id"
    )

    #: A MEGRENDELŐI keretszerződés módosításai - egy kereten több is lehet,
    #: mindegyik önálló papír (lásd models/keret_modositas.py).
    modositasok: Mapped[list["KeretModositas"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="KeretModositas.id"
    )

    client: Mapped["Client"] = relationship(back_populates="contracts")
    employee: Mapped["Employee"] = relationship(back_populates="contracts")
    vallalkozas: Mapped["Vallalkozas | None"] = relationship(back_populates="contracts")
    project: Mapped["Project | None"] = relationship(back_populates="contracts", foreign_keys=[project_id])
    project_code: Mapped["ProjectCode | None"] = relationship(foreign_keys=[project_code_id])
    project_codes: Mapped[list["ProjectCode"]] = relationship(
        back_populates="contract", foreign_keys="ProjectCode.contract_id"
    )


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


class ContractTetel(TimestampMixin, Base):
    """Egy ESETI szerződés EGY tétele: kinek a munkájára, melyik projekten.

    Ugyanaz a felépítés, mint a TIG-nél (lásd
    models/performance_certificate.py PerformanceCertificateTetel), és
    ugyanazért kell: a papír nem mindig egy ember egy projektjéről szól.

    - Egy projekten két stábtag munkáját ugyanaz a fél számlázza: egy
      szerződés, két tétel.
    - Három nap forgatásról egy számla (és egy TIG) készül: akkor egy
      szerződésnek is kell tartoznia hozzá, projektenként egy tétellel.

    A második eset miatt nem elég a Contract.project_id: az csak az "otthon"
    projekt (ahonnan a szerződés készült), a tényleges lefedettséget a tételek
    hordozzák.

    A `netto_osszeg` itt is opcionális: összevont szerződésnél nem mindig
    tudható, melyik nap mennyibe került - a szerződés fejösszege az igazság."""

    __tablename__ = "contract_tetelek"
    __table_args__ = (UniqueConstraint("contract_id", "project_id", "employee_id", name="uq_szerzodes_tetel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Egy (projekt, ember) párra legfeljebb EGY eseti szerződés szólhat - erre
    #: az adatbázis nem tud kényszert adni (több szerződésen át kellene
    #: néznie), ezért a végpont ellenőrzi.
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)

    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Ebből ennyi az övé - ha tudható")
    megnevezes: Mapped[str | None] = mapped_column(String(255))

    contract: Mapped["Contract"] = relationship(back_populates="tetelek")
    project: Mapped["Project"] = relationship()
    employee: Mapped["Employee"] = relationship()


class ContractPeriod(TimestampMixin, Base):
    """Egy keretszerződés ÉRVÉNYESSÉGI IDŐSZAKA - mettől meddig élt.

    Egy emberrel nem feltétlenül folyamatos a keretszerződéses viszony: van
    egy időszakra, aztán fél évig nincs, majd újra kötünk vele egyet. Ezért
    nem elég egy kezdet/vég dátumpár a szerződésen, hanem tetszőleges számú,
    egymást követő időszak tartozhat hozzá.

    A nyitott vég (veg IS NULL) azt jelenti: "azóta is él". A nyitott kezdet
    (kezdet IS NULL) azt, hogy "a kezdetektől" - ez a régi, dátum nélküli
    bejegyzéseknek kell.

    Ha egy keretszerződéshez EGYETLEN időszak sincs, az időbeli korlátozás
    nélkül érvényes (így viselkedett a rendszer az időszakok bevezetése
    előtt is) - lásd keretszerzodes_ervenyes()."""

    __tablename__ = "contract_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    kezdet: Mapped[date | None] = mapped_column(Date)
    veg: Mapped[date | None] = mapped_column(Date)
    megjegyzes: Mapped[str | None] = mapped_column(String(255))

    contract: Mapped["Contract"] = relationship(back_populates="idoszakok")


def idoszak_tartalmazza(idoszak: ContractPeriod, nap: date) -> bool:
    """Beleesik-e a nap ebbe az időszakba? A nyitott végek végtelent jelentenek."""
    if idoszak.kezdet is not None and nap < idoszak.kezdet:
        return False
    if idoszak.veg is not None and nap > idoszak.veg:
        return False
    return True


def keretszerzodes_ervenyes(szerzodes: Contract, nap: date | None = None) -> bool:
    """Érvényes-e ez a keretszerződés az adott NAPON?

    Ettől függ, hogy egy projekthez kell-e eseti szerződést kérni az embertől:
    ha a forgatás napján élt a keretszerződése, nem kell; ha épp nem élt (mert
    lejárt, vagy két időszak közé esik), akkor igen.

    Három feltétel egymás után:
    1. valódi keretszerződés-e egyáltalán (lásd megkotott_keretszerzodes),
    2. be van-e kapcsolva (aktiv),
    3. beleesik-e a nap valamelyik érvényességi időszakba - ha egyetlen
       időszak sincs felvéve, ez a lépés kimarad (korlátlan érvényesség).

    Nap nélkül a mai napot nézzük: "él-e most?"."""
    if not megkotott_keretszerzodes(szerzodes) or not szerzodes.aktiv:
        return False
    idoszakok = list(szerzodes.idoszakok or [])
    if not idoszakok:
        return True
    return any(idoszak_tartalmazza(i, nap or date.today()) for i in idoszakok)
