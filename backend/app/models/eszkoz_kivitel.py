"""Eszközkivitel - ki mit vitt el egy forgatásra, és mit hozott vissza.

A felhasználó kérése: egy bejelentkezés NÉLKÜLI, letisztult oldalon a
forgatásra kimenő ember egy 6 jegyű kóddal belép, és beírja, pontosan mit
visz ki (a forgatásra kiírt technika csak SÚGÓ - mást is vihet), majd
visszaérve azt, hogy mit hozott vissza (ott már súgó nélkül). A kettő
különbsége - mi nem jött vissza - csak a bejelentkezett kezelő oldalon
látszik (/eszkozkivitelek).

A kód a forgatás utolsó napja után 48 óráig él (lásd
api/routes/eszkoz_kivitel.kivitel_ervenyes) - amíg él, a lezárt
visszahozatal is újranyitható belépéssel. Az "admin" kód mindig él, és
egy projekt nélküli TESZT-kivitelbe lép be.

A diszpó-kiküldésbe SZÁNDÉKOSAN nincs bekötve: előbb önállóan épül fel és
tesztelődik (a felhasználó kérése), a kódot addig a kezelő oldalon lehet
generálni és onnan kiadni."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class EszkozKivitel(TimestampMixin, Base):
    __tablename__ = "eszkoz_kivitelek"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Melyik forgatáshoz tartozik. None = az "admin" kódos teszt-kivitel.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    #: A belépő kód: 6 számjegy, vagy a mindig élő "admin" (teszt).
    kod: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    teszt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: A folyamat fázisa (a felhasználó kérése, hogy ne lehessen csalni):
    #:   "kivitel" - csak kivitel írható;
    #:   "vissza"  - a kivitel lezárva, csak visszahozatal írható (a kivitt
    #:               lista a publikus oldalon már nem látszik; pót-kivitel
    #:               csak NÖVELÉSKÉNT vihető fel, a korábbiak nélkül);
    #:   "lezart"  - minden lezárva, csak a kezelő oldal látja.
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="kivitel")
    #: A visszahozatal lezárásakor megadható észrevétel (eszközökről,
    #: forgatásról) - kihagyható.
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    #: Mikor zárták le a kivitelt, illetve a visszahozatalt - a kezelő
    #: oldalon látszik (a felhasználó kérése).
    kivitel_lezarva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vissza_lezarva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: NEM LELTÁRI eszköz (bérelt, külsős cucc) szabad szöveggel - külön a
    #: kivitelnél és a visszahozatalnál (a felhasználó kérése). A vissza-
    #: hozatal fázisban a kivitelé már nem látszik (csalás-védelem).
    kulso_kivitel: Mapped[str | None] = mapped_column(Text)
    kulso_vissza: Mapped[str | None] = mapped_column(Text)
    #: HIÁNY-KEZELÉS (a felhasználó kérése): ha a kód lejárta után is maradt
    #: hiány (kevesebb jött vissza, mint amennyi kiment), a dashboard jól
    #: láthatóan kiírja - ott magyarázat írható (mi lett a megoldás), és a
    #: "kész" jelöléssel vehető le a figyelmeztetés.
    hiany_megoldas: Mapped[str | None] = mapped_column(Text)
    hiany_megoldva: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    project = relationship("Project")
    tetelek: Mapped[list["EszkozKivitelTetel"]] = relationship(
        back_populates="kivitel", cascade="all, delete-orphan", order_by="EszkozKivitelTetel.id"
    )


class EszkozKivitelTetel(TimestampMixin, Base):
    """Egy eszköz egy kivitelen: hány darab ment ki, és hány jött vissza."""

    __tablename__ = "eszkoz_kivitel_tetelek"
    __table_args__ = (UniqueConstraint("kivitel_id", "equipment_id", name="uq_kivitel_eszkoz"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kivitel_id: Mapped[int] = mapped_column(ForeignKey("eszkoz_kivitelek.id"), nullable=False, index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    kivitt_db: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visszahozott_db: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    kivitel: Mapped[EszkozKivitel] = relationship(back_populates="tetelek")
    equipment = relationship("Equipment")
