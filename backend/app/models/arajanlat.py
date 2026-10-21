"""Árajánlat-készítő: mentett ajánlatok/sablonok és az alap tétel-katalógus.

A felhasználó kérése: külön oldal (saját hozzáféréssel), ahol árajánlat
készíthető a megszokott sablon-kinézettel; az alap tételek (kamera szett,
operatőr, utómunka...) egy katalógusból egy kattintással hozzáadhatók; egy
kész ajánlat SABLONKÉNT is elmenthető ("1 kamerás esemény videó"), amit
később vissza lehet hívni és átszerkeszteni; és van egy HYPE/ContentBee
kapcsoló, ami a sarok-logót (és a cégadatokat) váltja.

MIÉRT EGY JSON-MEZŐ a tartalom? Az ajánlat szerkezete mély és szabad
(blokkok > szekciók > tételek + fejléc + jegyzetek), és mindig EGYBEN
szerkesztik/mentik - sorokra bontva minden mentés több tucat írás lenne,
miközben semmilyen lekérdezés nem a tételekre megy. A kereshető/lista-adat
(név, brand, sablon-e, ügyfél) külön oszlop."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

#: A kapcsoló két állása - a frontend logót/fejlécet vált rá.
BRAND_HYPE = "hype"
BRAND_CONTENTBEE = "contentbee"


class Arajanlat(TimestampMixin, Base):
    """Egy mentett árajánlat - vagy ajánlat-SABLON (sablon=True).

    A kettő szándékosan egy tábla: a sablon ugyanolyan ajánlat, csak nem egy
    konkrét ügyfélnek szól, hanem kiindulási alap ("1 kamerás esemény videó") -
    megnyitáskor a tartalma másolódik egy új ajánlatba."""

    __tablename__ = "arajanlatok"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Az ajánlat (vagy a sablon) neve a listában.
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Sablon-e (visszahívható kiindulás), vagy konkrét, kiadott ajánlat.
    sablon: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: "hype" | "contentbee" - melyik cég nevében megy ki (logó a sarokban).
    brand: Mapped[str] = mapped_column(String(20), nullable=False, default=BRAND_HYPE)
    #: Kinek szól - a listában látszik, a tartalomból másolódik ide mentéskor.
    ugyfel: Mapped[str | None] = mapped_column(String(255))
    #: A végösszeg (amilyen pénznemben az ajánlat készült) - a lista mutatja,
    #: a szerkesztő számolja és mentéskor írja.
    vegosszeg: Mapped[float | None] = mapped_column(Numeric(14, 2))
    #: A TELJES szerkesztő-állapot: fejléc, felek, blokkok (szekciókkal és
    #: tételekkel), kedvezmény, ÁFA, jegyzetek - lásd a modul leírását.
    adat: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ArajanlatTetel(TimestampMixin, Base):
    """Egy ALAP TÉTEL a katalógusban - az ajánlatba egy kattintással kerül be.

    Nem kapcsolódik a mentett ajánlatokhoz: a hozzáadáskor az értékei
    BEMÁSOLÓDNAK az ajánlat JSON-jába, tehát a katalógus későbbi átárazása a
    már kiadott ajánlatokat nem írja át."""

    __tablename__ = "arajanlat_tetelek"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Az ajánlaton a tétel alá kerülő megjegyzés (pl. "Canon C70 vagy C300").
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    #: Melyik szekcióba való alapból ("Technika", "Utómunka", "Emberi erőforrás").
    szekcio: Mapped[str | None] = mapped_column(String(100))
    egysegar: Mapped[float | None] = mapped_column(Numeric(12, 2))
    #: A katalógus-lista sorrendje (kisebb elöl).
    sorrend: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
