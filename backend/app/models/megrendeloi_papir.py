"""Megrendelői papírok: eseti szerződés és teljesítési igazolás a MEGRENDELŐ
felé - a projektkódhoz kötve.

Ugyanaz a rendszer, mint az alvállalkozói oldalon (lásd models/contract.py és
performance_certificate.py), csak a másik irányba: ott mi fizetünk, itt minket
fizetnek. A szerkezet szándékosan egyezik - állapot, generált fájl, aláírva
visszakapott fájl, kihagyás indoka -, mert a folyamat is ugyanaz, és két
eltérő alakú papír-nyilvántartás két külön szabályrendszert jelentene.

MIÉRT KÜLÖN MODELLEK, ÉS NEM A ProjectCode MEZŐI? A ProjectCode-on ott van a
Notionból örökölt lapos mezőkészlet (`szerzodes_statusza`, `tig_statusza`,
`szerzodes_url`...), de az csak SZÖVEG: nincs mögötte állapotgép, nincs
tárhely-kulcs a fájlcseréhez, nincs kihagyás-indok, és nem bírja el, hogy egy
projektkódhoz több papír is tartozzon. Azok a mezők az import miatt maradnak
meg; az élő folyamat innen megy.

A CÉGADATOK MÁSOLATBAN vannak a papíron (`ceg_neve`, `szekhely`, `adoszam`,
`kepviselo`, `nyilvantartasi_szam`) - nem a Client-re mutató hivatkozásból
olvassuk ki kiküldéskor. Ez szándékos: a papír azt kell hogy őrizze, ami RAJTA
van. Ha a megrendelő fél év múlva székhelyet vált, a régi szerződés attól még
a régi székhellyel kelt - egy élő hivatkozás visszamenőleg átírná a
történelmet.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: A papír útja. Ugyanaz a szókészlet, mint az alvállalkozói oldalon, hogy a
#: két felület ugyanazt jelentse ugyanazzal a szóval.
ALLAPOTOK: tuple[str, ...] = ("Készítés alatt", "Kiküldve", "Kihagyva", "Van már papír")
#: Amiből már nincs teendő - a fázis-nézet ezeket tekinti lezártnak.
LEZART_ALLAPOTOK: frozenset[str] = frozenset({"Kiküldve", "Kihagyva", "Van már papír"})


def papir_kesz(papir) -> bool:
    """Le van-e zárva ez a papír? EGY szabály, mindenhol ugyanaz.

    Két dolog zárja le:

    1. az ÁLLAPOTA (lásd LEZART_ALLAPOTOK) - innen ment ki, kihagytuk, vagy
       kimondtuk, hogy van már papír;
    2. az ALÁÍRT PÉLDÁNY megléte - az a legerősebb bizonyíték, bármit is mond
       az állapot-mező.

    A második azért kell, mert a régi sorokon az állapot elmaradt a
    valóságtól: aki feltöltötte az aláírt szerződést egy piszkozatba, annak a
    papírja "Készítés alatt" maradt, a projektkód pedig "Szerződés hiányzik"-ot
    írt ki - miközben az aláírt papír ott volt megnyithatóan a kártyán. A
    feltöltés MA már át is állítja az állapotot (lásd
    routes/megrendeloi_papirok.py), ez a szabály a KORÁBBAN keletkezett
    sorokra is érvényes, adatjavítás nélkül."""
    if papir is None:
        return False
    return bool(papir.alairt_file_url) or papir.allapot in LEZART_ALLAPOTOK


class MegrendeloiSzerzodes(TimestampMixin, Base):
    """Eseti szerződés a megrendelővel, egy projektkódra.

    Egy projektkódhoz több is tartozhat: előfordul, hogy ugyanarra a
    gyártásra két cég szerződik (társfinanszírozás), vagy hogy egy elrontott
    papírt újra kell kezdeni. Ezért nincs egyediség-megkötés a
    projektkódon."""

    __tablename__ = "megrendeloi_szerzodesek"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False, index=True)
    #: Kivel szerződünk. A cégadatokat innen töltjük ELŐ, de a papírra a lenti
    #: másolat kerül (lásd a modul leírását).
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    #: Ha keretszerződés alapján megy, ide mutat - a felület ebből tudja
    #: kiírni, hogy "keretszerződés fedi".
    keretszerzodes_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))
    #: Melyik kontakt e-mail címére ment ki.
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))

    # --- a papírra kerülő adatok (MÁSOLAT, lásd a modul leírását) ---
    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(500))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    kepviselo: Mapped[str | None] = mapped_column(String(255))
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))

    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    projekt_nev: Mapped[str | None] = mapped_column(String(255), comment="A szerződésen szereplő projektnév")
    teljesites_szoveg: Mapped[str | None] = mapped_column(String(500), comment="Teljesítés ideje - szabad szöveg")
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2))
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)
    keltezes: Mapped[date | None] = mapped_column(Date)

    allapot: Mapped[str | None] = mapped_column(String(50), default="Készítés alatt")
    #: A generált (vagy feltöltött) papír.
    file_url: Mapped[str | None] = mapped_column(String(500))
    file_storage_key: Mapped[str | None] = mapped_column(String(500))
    #: Az ALÁÍRVA visszakapott példány - amíg nincs, a papír "aláírásra vár".
    alairt_file_url: Mapped[str | None] = mapped_column(String(500))
    alairt_file_storage_key: Mapped[str | None] = mapped_column(String(500))

    kihagyas_oka: Mapped[str | None] = mapped_column(Text)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    project_code: Mapped["ProjectCode"] = relationship()
    client: Mapped["Client | None"] = relationship()
    keretszerzodes: Mapped["Contract | None"] = relationship()
    contact: Mapped["Contact | None"] = relationship()


class MegrendeloiTig(TimestampMixin, Base):
    """Teljesítési igazolás a megrendelő felé, egy projektkódra.

    Ugyanaz a mezőkészlet, mint a szerződésé - a papírok azonos adatokat
    viselnek, csak más sablonnal mennek ki."""

    __tablename__ = "megrendeloi_tigek"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False, index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    keretszerzodes_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))

    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(500))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    kepviselo: Mapped[str | None] = mapped_column(String(255))
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))

    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    projekt_nev: Mapped[str | None] = mapped_column(String(255))
    teljesites_szoveg: Mapped[str | None] = mapped_column(String(500))
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2))
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)
    keltezes: Mapped[date | None] = mapped_column(Date)

    allapot: Mapped[str | None] = mapped_column(String(50), default="Készítés alatt")
    file_url: Mapped[str | None] = mapped_column(String(500))
    file_storage_key: Mapped[str | None] = mapped_column(String(500))
    alairt_file_url: Mapped[str | None] = mapped_column(String(500))
    alairt_file_storage_key: Mapped[str | None] = mapped_column(String(500))

    kihagyas_oka: Mapped[str | None] = mapped_column(Text)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    project_code: Mapped["ProjectCode"] = relationship()
    client: Mapped["Client | None"] = relationship()
    keretszerzodes: Mapped["Contract | None"] = relationship()
    contact: Mapped["Contact | None"] = relationship()
