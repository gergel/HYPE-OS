"""Krumpello - önálló pénzügyi nyilvántartás, a HYPE OS-en BELÜL, de attól
elválasztva.

Miért külön modellek, és miért nem a meglévő Expense/Revenue táblák?

A Krumpello egy másik üzlet (utcai étel), másik logikával: nincs projektkód,
nincs ügyfél, nincs TIG és nincs szerződés - a bevétel NAPI kassza-zárás
(készpénz/kártya bontásban), a kiadás pedig egy egyszerű kifizetés-lista. Ha
ezek a HYPE pénzügyeibe kerülnének, minden HYPE-összesítő (éves kiadás, havi
trend, projekt-költség) hamis lenne, és fordítva: a Krumpello képét
elhomályosítanák a produkciós tételek. Egy közös tábla + egy "melyik cég"
oszlop csak látszatmegtakarítás lenne - a két oldal MINDEN lekérdezésében
szűrni kellene rá, és egyetlen kifelejtett szűrő összekeverné a két kasszát.

A szerkezet a valóságot követi (lásd a "HYPE PRODUCTIONS KFT. 2026 - PÉNZÜGY"
munkafüzet "KRUMPELLO - KASSZA" és "KRUMPELLO - MUNKABÉR" lapjait), mert a
napi munka ott folyik, és az itteni adatnak azzal kell egyeznie.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: Honnan ment ki a pénz. Nem csak könyvelési részlet: a három forrásnak külön
#: egyenlege van (számla, készpénz, extra), és a felület is így összesít.
KIADAS_FORRASOK: tuple[str, ...] = ("utalas", "keszpenz", "extra")

#: Hogyan volt bejelentve valaki egy adott napon.
#:
#: Ez nem adminisztratív cimke, hanem a KIFIZETÉS MÓDJÁT dönti el: a bejelentett
#: napi bér utalással megy (az szerepel a bérszámfejtésben), a fölötte lévő
#: rész pedig készpénzben. Bejelentés nélkül az egész nap készpénz.
BEJELENTESEK: tuple[str, ...] = ("efo", "hatarozott", "nincs")

#: Emberi címkék - a felület és a napló ezt írja ki.
BEJELENTES_CIMKEK: dict[str, str] = {
    "efo": "EFO (egyszerűsített foglalkoztatás)",
    "hatarozott": "Határozott idejű munkaszerződés",
    "nincs": "Nem volt bejelentve",
}

#: Ha se a napon, se az időszakon nincs megadva, ezt vesszük.
ALAP_BEJELENTES = "nincs"

#: Az "extra" a kulcs fogalom az egész modulban: olyan bevétel vagy kiadás,
#: amihez NINCS számla, ami megmagyarázná, honnan jött vagy hova ment. Ezek
#: nem hibák - a valóságban léteznek -, de külön kell látszaniuk, mert csak
#: együtt adják ki, hogy az elszámolatlan pénzmozgás pluszban vagy mínuszban
#: áll-e (lásd services/krumpello_osszesito.py EXTRA EGYENLEG).
EXTRA_FORRAS = "extra"


class KrumpelloNap(TimestampMixin, Base):
    """Egy nap kassza-zárása - naponta PONTOSAN egy sor.

    A napi bontás nem díszítés: a kassza készpénz-egyenlege csak akkor
    ellenőrizhető a fiókban lévő pénzzel, ha naponta zárnak. Az egyediség
    (uq_krumpello_nap_datum) ezért adatbázis-szintű: két sor ugyanarra a napra
    azt jelentené, hogy az egyik zárás elveszett vagy duplán számít.

    A bruttó/nettó SZÁNDÉKOSAN külön oszlop, nem számoljuk egyikből a másikat:
    a pénztárgép többféle áfakulcsú tételt üt (5% / 18% / 27%), a napi bontás
    pedig már az ő összesítője - egy visszaszámolt "átlagáfa" néhány forinttal
    mindig eltérne a bevallottól.
    """

    __tablename__ = "krumpello_napok"
    __table_args__ = (UniqueConstraint("datum", name="uq_krumpello_nap_datum"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    brutto_kp: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Bruttó bevétel készpénzben")
    brutto_kartya: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Bruttó bevétel kártyával")
    netto_kp: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó bevétel készpénzben")
    netto_kartya: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó bevétel kártyával")

    # A borravaló nem árbevétel: a dolgozóké. Azért van mégis itt, mert a
    # kasszában fizikailag benne van, tehát a készpénz-egyenleg csak vele
    # együtt jön ki - de az árbevétel-összesítőkből kimarad.
    borravalo_kp: Mapped[float | None] = mapped_column(Numeric(12, 2))
    borravalo_kartya: Mapped[float | None] = mapped_column(Numeric(12, 2))

    #: Számlával NEM fedett bevétel aznap (lásd EXTRA_FORRAS).
    extra: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Számla nélküli bevétel")

    megjegyzes: Mapped[str | None] = mapped_column(Text)


class KrumpelloKiadas(TimestampMixin, Base):
    """Egy kifizetés. A `forras` mondja meg, melyik kasszából ment ki.

    Az "extra" forrásnál a nettó és az áfa üres marad: ott nincs számla,
    amiből ki lehetne olvasni - egyetlen összeg van, amit valaki kifizetett.
    Ezért NEM kényszerítjük ki a nettó+áfa=bruttó egyenlőséget: a valóságban
    kerekített, néha hiányos számlaadatokkal dolgozunk, és egy szigorú
    ellenőrzés csak arra tanítaná a felhasználót, hogy kitaláljon egy számot.
    """

    __tablename__ = "krumpello_kiadasok"

    id: Mapped[int] = mapped_column(primary_key=True)
    forras: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="utalas / keszpenz / extra")

    kedvezmenyezett: Mapped[str] = mapped_column(String(255), nullable=False, comment="Kinek fizettünk")
    datum: Mapped[date | None] = mapped_column(Date, index=True)
    megnevezes: Mapped[str | None] = mapped_column(String(500), comment="Mire ment el")

    netto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    afa: Mapped[float | None] = mapped_column(Numeric(12, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(12, 2))

    megjegyzes: Mapped[str | None] = mapped_column(Text)


class KrumpelloDolgozo(TimestampMixin, Base):
    """Aki a Krumpellóban dolgozik, órabérben.

    Külön tábla, nem a HYPE Employee: itt jellemzően diákok és alkalmi
    munkatársak vannak, akiknek a produkciós rendszerben (stáblista, TIG,
    szerződés, jogosultság) semmi keresnivalójuk. Aki mindkét helyen dolgozik,
    az `employee_id`-vel összeköthető - de ez opcionális, és semmi nem múlik
    rajta: a Krumpello elszámolása a saját nevével is teljes.
    """

    __tablename__ = "krumpello_dolgozok"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Az utolsó ismert órabér - CSAK javaslat az új óra-sorhoz. A tényleges
    #: órabér mindig a sorban van (lásd KrumpelloMunkaora.orabar), mert
    #: időben változik, és egy régi hónapot nem szabad visszamenőleg átárazni.
    alap_orabar: Mapped[float | None] = mapped_column(Numeric(12, 2))
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    munkaorak: Mapped[list["KrumpelloMunkaora"]] = relationship(
        back_populates="dolgozo", cascade="all, delete-orphan"
    )
    idoszakok: Mapped[list["KrumpelloIdoszak"]] = relationship(
        back_populates="dolgozo", cascade="all, delete-orphan", order_by="KrumpelloIdoszak.kezdet"
    )


class KrumpelloIdoszak(TimestampMixin, Base):
    """Egy ember FOGLALKOZTATÁSI IDŐSZAKA: mettől meddig, milyen bejelentéssel.

    Miért kell? Mert a Krumpellóban ugyanaz az ember év közben többféleképpen
    dolgozik: nyáron EFO-val pár hétig, ősztől határozott idejű
    munkaszerződéssel, közben pedig van olyan nap, amire egyáltalán nincs
    bejelentve. A bejelentés módja és a bejelentett napi bér nem az EMBER
    tulajdonsága, hanem az IDŐSZAKÉ - egy közös mező a dolgozón visszamenőleg
    átírná a korábbi hetek elszámolását.

    Az időszak egyben az ELSZÁMOLÁS EGYSÉGE is: a kifizetés a gyakorlatban egy
    időszakra szól ("július 22. - augusztus 3."), nem naponta.

    A napokat NEM idegen kulcs köti ide, hanem a DÁTUM: a
    (dolgozó, kezdet..vég) intervallumba eső munkaóra-sorok tartoznak az
    időszakhoz. Így egy utólag felvitt nap magától a helyére kerül, és nem
    fordulhat elő, hogy egy sor kimarad az elszámolásból, mert elfelejtették
    hozzákötni. Cserébe egy emberre az időszakok nem fedhetik egymást - ezt a
    mentés ellenőrzi (lásd routes/krumpello.py).

    A nyitott vég (`veg IS NULL`) azt jelenti: "azóta is tart".
    """

    __tablename__ = "krumpello_idoszakok"

    id: Mapped[int] = mapped_column(primary_key=True)
    dolgozo_id: Mapped[int] = mapped_column(ForeignKey("krumpello_dolgozok.id"), nullable=False, index=True)

    kezdet: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    veg: Mapped[date | None] = mapped_column(Date, comment="Üresen: azóta is tart")

    #: Hogyan van bejelentve EBBEN az időszakban (lásd BEJELENTESEK).
    bejelentes: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ALAP_BEJELENTES, comment="efo / hatarozott / nincs"
    )
    #: A bejelentett ALAP NAPI BÉR - ez megy utalással, a fölötte lévő rész
    #: készpénzben. Bejelentés nélkül nincs értelme, ilyenkor üres.
    napi_ber: Mapped[float | None] = mapped_column(
        Numeric(12, 2), comment="A bejelentett napi bér, ami utalással megy"
    )

    #: Az időszak neve, ha van ("Nyári szezon") - csak a felület kedvéért.
    nev: Mapped[str | None] = mapped_column(String(255))
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    dolgozo: Mapped["KrumpelloDolgozo"] = relationship(back_populates="idoszakok")


class KrumpelloMunkaora(TimestampMixin, Base):
    """Egy ember egy napja: hány órát dolgozott, milyen órabéren.

    A `fizetes` TÁROLT mező, nem számított: az óra × órabér a jellemző eset, de
    nem mindig - kerekítés, megbeszélt napi átalány, pótlék. Ha a felület
    kiszámolná, minden ilyen eset kézi felülírást kívánna, és a kifizetett
    összeg nem egyezne a nyilvántartottal. A mentés kitölti, ha üresen hagyják
    (lásd routes/krumpello.py), tehát a szokásos esetben nem kell számolgatni.

    A borravaló itt is elkülönül: az nem bér, hanem a vendégektől kapott,
    továbbadott pénz - de ugyanannak az embernek ugyanarra a napra tartozik,
    ezért egy sorban van vele.
    """

    __tablename__ = "krumpello_munkaorak"

    id: Mapped[int] = mapped_column(primary_key=True)
    dolgozo_id: Mapped[int] = mapped_column(ForeignKey("krumpello_dolgozok.id"), nullable=False, index=True)
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    ora: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="Ledolgozott órák száma")
    orabar: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Az ADOTT napi órabér")
    fizetes: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="A napra járó bér")
    borravalo: Mapped[float | None] = mapped_column(Numeric(12, 2))
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    #: Hogyan volt bejelentve EZEN a napon (lásd BEJELENTESEK).
    #:
    #: Üresen hagyva az időszakából örökli (lásd KrumpelloIdoszak és
    #: services/krumpello_munkaber.py). Azért lehet mégis naponta felülírni,
    #: mert a valóságban előfordul kivétel: egy beugrás a szerződéses időszak
    #: közepén, amire aznap nem jelentették be.
    bejelentes: Mapped[str | None] = mapped_column(String(20), comment="efo / hatarozott / nincs")
    #: A bejelentett napi bér EZEN a napon. Üresen az időszakéból örökli.
    bejelentett_napi_ber: Mapped[float | None] = mapped_column(
        Numeric(12, 2), comment="Az utalással fizetett alap napi bér"
    )

    #: Kifizettük-e már ezt a napot.
    #:
    #: Miért a NAPON van, és nem egy külön "kifizetés" rekordon? Mert a kérdés,
    #: amire válaszolni kell, mindig egy napra vonatkozik: "ez a nap benne volt
    #: már egy kifizetésben?" Kifizetés-rekordokból ezt csak összeadogatással
    #: lehetne kitalálni, és egy elmaradt nap (pl. amit utólag vittek fel egy
    #: már kifizetett időszakba) némán beleolvadna egy korábbi összegbe.
    #:
    #: A kifizetés a gyakorlatban IDŐSZAKONKÉNT történik (lásd a kassza-táblázat
    #: "ZÁRÁS" sorait), ezért a felület tömegesen is tudja jelölni egy ember
    #: adott időszakát - de a jelölés akkor is soronként kerül fel, hogy egy
    #: később hozzáírt nap ne látszódjon automatikusan kifizetettnek.
    kifizetve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Mikor fizettük ki. A jelölés napja csak alapérték - a tényleges utalás
    #: dátuma ettől eltérhet, ezért átírható.
    kifizetes_datuma: Mapped[date | None] = mapped_column(Date)

    dolgozo: Mapped["KrumpelloDolgozo"] = relationship(back_populates="munkaorak")
