"""Visszatérő kötelezettségek: előfizetések, biztosítások, bérletek.

Ami közös bennük, és amiért egy tábla írja le mindet: van egy FORDULÓJUK (egy
nap, amikor megújul vagy lejár), van egy FELELŐSÜK, kerül valamennyibe, és
minden fordulónál keletkezik egy számla, amit el kell tenni. A különbség csak
a ciklus hossza - havi vagy éves -, meg hogy minek hívjuk (`tipus`).

Két rétegű, és ez a lényeg:

1. a KÖTELEZETTSÉG a törzsadat ("Adobe Creative Cloud, éves, szeptember 3.,
   felelős Vidor Geri") - ez nem változik hónapról hónapra;
2. az IDŐSZAK (KotelezettsegIdoszak) egyetlen konkrét esedékesség ("2026.
   szeptember 3-i forduló") - ide kerül, hogy PONTOSAN mennyibe került, és ide
   kerül a számla is.

Azért kell a kettő külön, mert a törzsadatban lévő ár csak becslés (a
devizaárfolyam és az áremelés miatt szinte sosem pontos), a könyveléshez
viszont a ténylegesen levont összeg kell - és az fordulónként más. A havi
előfizetés így havonta "vár" egy összeget, az éves évente egyet.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class KotelezettsegTipus(StrEnum):
    """Mi ez a kötelezettség.

    Csoportosítás és szűrés - a működést (forduló, számla, értesítés) nem
    befolyásolja, mert az mindegyiknél ugyanaz. Két helyen mégis a felület
    tagolását adja: az E-Rezsi oldal az ELOFIZETES sorokat mutatja, az autó
    lapja pedig a hozzá tartozó FORGALMI és BIZTOSITAS határidőket."""

    ELOFIZETES = "elofizetes"
    BIZTOSITAS = "biztositas"
    #: Forgalmi engedély / műszaki érvényessége - autóknál.
    FORGALMI = "forgalmi"
    BERLET = "berlet"
    EGYEB = "egyeb"


class KotelezettsegCiklus(StrEnum):
    """Milyen gyakran fordul.

    Az EGYSZERI a határozott idejű szerződés: nem újul meg magától, egyetlen
    lejárata van (`kovetkezo_fordulo`), és annál nem képződik újabb időszak -
    ott az a teendő, hogy dönteni kell a meghosszabbításáról."""

    HAVI = "havi"
    EVES = "eves"
    EGYSZERI = "egyszeri"


class Kotelezettseg(TimestampMixin, Base):
    """Egy visszatérő kötelezettség törzsadata."""

    __tablename__ = "kotelezettsegek"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: A konkrét csomag ("Creative Cloud Összes alkalmazás, 100 GB"), ha van -
    #: ugyanannak a szolgáltatónak több előfizetése is futhat egyszerre.
    csomag: Mapped[str | None] = mapped_column(String(500))

    tipus: Mapped[str] = mapped_column(String(20), nullable=False, default=KotelezettsegTipus.ELOFIZETES)
    ciklus: Mapped[str] = mapped_column(String(20), nullable=False, default=KotelezettsegCiklus.HAVI)

    # ── A forduló ─────────────────────────────────────────────────────────────
    # Kétféleképpen ismerhetjük, és a kettő nem ugyanaz:
    #
    #   `fordulo_nap` (+ éveseknél `fordulo_honap`) a MINTA: "minden hónap
    #   7-én", "minden szeptember 3-án". Ebből bármelyik évre kiszámolható a
    #   következő esedékesség.
    #
    #   `kovetkezo_fordulo` egy KONKRÉT dátum: "2029. 06. 17.". Ez erősebb a
    #   mintánál, mert lehet több évre előre kifizetve (egy négy évre megvett
    #   domain nem évente esedékes), és a határozott idejű szerződés lejárata
    #   is ez. Ha ki van töltve és még nem múlt el, ez a következő forduló;
    #   miután elmúlt, a minta viszi tovább (lásd services/kotelezettseg.py).
    fordulo_nap: Mapped[int | None] = mapped_column(comment="A hónap napja, 1-31")
    fordulo_honap: Mapped[int | None] = mapped_column(comment="Éves ciklusnál a hónap, 1-12")
    kovetkezo_fordulo: Mapped[date | None] = mapped_column(
        Date, comment="Konkrét következő forduló / lejárat - erősebb a mintánál"
    )
    #: Mikortól él. Ennél régebbi időszakot nem generálunk - egy most felvitt,
    #: évek óta futó előfizetéshez nem akarunk visszamenőleg 60 üres hónapot.
    kezdet: Mapped[date | None] = mapped_column(Date)

    #: Melyik területé a költség ("utómunka", "gyártás", "céges"…) - a
    #: táblázatban ez volt az "Osztály" oszlop.
    osztaly: Mapped[str | None] = mapped_column(String(100), index=True)
    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), index=True)
    aktiv: Mapped[bool] = mapped_column(nullable=False, default=True)
    #: Ha ez egy AUTÓ határideje (forgalmi, kötelező biztosítás), akkor melyik
    #: autóé. Az autó lapja ezeket mutatja - de a lejárat-figyelés,
    #: az értesítés és a feladat ugyanaz, mint bármelyik más kötelezettségnél
    #: (lásd models/auto.py).
    auto_id: Mapped[int | None] = mapped_column(ForeignKey("autok.id"), index=True)

    # ── Ár ────────────────────────────────────────────────────────────────────
    # Ez a VÁRT ár (a szolgáltató árlistája), nem a tényleges terhelés: azt
    # fordulónként az időszak `osszeg` mezője hordozza. Devizás előfizetésnél a
    # kettő szinte sosem egyezik, ezért nem közös mező.
    ar_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ar_penznem: Mapped[str] = mapped_column(String(3), nullable=False, default="HUF")
    #: A táblázatból hozott forintosított becslés - tájékoztató, nem számolunk
    #: vele (nincs a rendszerben árfolyam-forrás).
    huf_becsles_honap: Mapped[float | None] = mapped_column(Numeric(12, 2))
    huf_becsles_ev: Mapped[float | None] = mapped_column(Numeric(12, 2))

    #: Honnan szerezhető be a számla (email cím, letöltő link, "Ádám fiókjából").
    szamla_forras: Mapped[str | None] = mapped_column(Text)
    #: Melyik kártyáról vonják ("-9766").
    kartya: Mapped[str | None] = mapped_column(String(100))
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    #: Hány nappal a forduló előtt szóljon. Ez a "értesít, amikor lejár":
    #: ennyi nappal előtte keletkezik a feladat és az értesítés a felelősnek
    #: (lásd services/kotelezettseg.py ensure_feladatok).
    ertesites_napokkal: Mapped[int] = mapped_column(nullable=False, default=14)

    felelos: Mapped["Employee | None"] = relationship()
    auto: Mapped["Auto | None"] = relationship(back_populates="kotelezettsegek")
    idoszakok: Mapped[list["KotelezettsegIdoszak"]] = relationship(
        back_populates="kotelezettseg",
        cascade="all, delete-orphan",
        order_by="KotelezettsegIdoszak.esedekesseg.desc()",
    )


class KotelezettsegIdoszak(TimestampMixin, Base):
    """Egy konkrét esedékesség: a havi előfizetés egy hónapja, az évesnek egy
    éve, a határozott idejű szerződésnek a lejárata.

    Az egyediség az ESEDÉKESSÉG dátumára szól, nem az (év, hónap) párra: így a
    havi és az éves ciklus ugyanabban a táblában elfér, és nem kell a hónap
    mezőt üresen hagyni az éveseknél (egy NULL-t tartalmazó egyediség-megkötés
    a PostgreSQL-ben amúgy sem szűrné ki az ismétlődést)."""

    __tablename__ = "kotelezettseg_idoszakok"
    __table_args__ = (
        UniqueConstraint("kotelezettseg_id", "esedekesseg", name="uq_kotelezettseg_idoszak_esedekesseg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kotelezettseg_id: Mapped[int] = mapped_column(ForeignKey("kotelezettsegek.id"), nullable=False, index=True)
    esedekesseg: Mapped[date] = mapped_column(Date, nullable=False)

    #: Amennyit TÉNYLEGESEN levontak. Amíg üres, az időszak teendő.
    osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(3), nullable=False, default="HUF")
    #: Ha devizás a terhelés, ennyi forint ment el ténylegesen - ezt a
    #: bankszámla mutatja meg, nem tudjuk kiszámolni.
    huf_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    fizetve: Mapped[bool] = mapped_column(nullable=False, default=False)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    kotelezettseg: Mapped["Kotelezettseg"] = relationship(back_populates="idoszakok")
