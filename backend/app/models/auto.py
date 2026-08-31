"""Céges autók: mikor jár le a papírja, és mennyit költünk rá.

Az autó két dolgot kíván, és mindkettőt MÁS rendszer szolgálja ki - ezért ez a
tábla szándékosan sovány, csak magát a járművet írja le:

1. HATÁRIDŐK (forgalmi, biztosítás): ezek `Kotelezettseg` sorok, amiknek ki van
   töltve az `auto_id`-ja. Azért nem külön dátumoszlopok az autón, mert a
   lejáratról szóló egész gépezet - értesítés a felelősnek, feladat a
   fordulóig hátralévő időn belül, a fordulónkénti számla és a ténylegesen
   fizetett összeg - már meg van írva a kötelezettségekhez, és a kötelező
   biztosítás pontosan az: évente forduló, számlás kötelezettség (lásd
   models/kotelezettseg.py, services/kotelezettseg.py).

2. KÖLTSÉGEK (tankolás, szerviz, autópálya-matrica): ezek `Expense` sorok,
   amiknek ki van töltve az `auto_id`-ja. Azért nem saját táblában, mert a
   kérés az volt, hogy az itt felvezetett kiadás a Pénzügy összesítő
   kiadásaiban IS jelenjen meg - ha külön tábla lenne, azt oda szinkronizálni
   kellene, és a két szám előbb-utóbb szétcsúszna. Így viszont nincs mit
   szinkronizálni: a kiadás EGY sor, amit az autó oldala csak leszűrve mutat.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Auto(TimestampMixin, Base):
    """Egy céges autó."""

    __tablename__ = "autok"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A rendszám az azonosító, amit mindenki használ - ezért kötelező és egyedi.
    rendszam: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    megnevezes: Mapped[str | None] = mapped_column(String(255), comment="Pl. Ford Transit - gyártásos busz")
    tipus: Mapped[str | None] = mapped_column(String(255), comment="Márka és típus")
    evjarat: Mapped[int | None] = mapped_column()
    #: Kilométeróra-állás az utolsó feljegyzéskor - tájékoztató.
    km_ora: Mapped[int | None] = mapped_column()

    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), index=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    felelos: Mapped["Employee | None"] = relationship()
    #: A jármű határidői (forgalmi, biztosítás) - lásd a modul kommentjét.
    kotelezettsegek: Mapped[list["Kotelezettseg"]] = relationship(
        back_populates="auto", cascade="all, delete-orphan"
    )
    #: A járműre könyvelt kiadások. Ugyanezek a sorok a Pénzügy kiadásai közt
    #: is ott vannak - nem másolat, ugyanaz a rekord.
    kiadasok: Mapped[list["Expense"]] = relationship(back_populates="auto")
    #: A járműhöz felvezetett teendők (lásd AutoTeendo) - az autóval együtt
    #: törlődnek.
    teendok: Mapped[list["AutoTeendo"]] = relationship(
        back_populates="auto", order_by="AutoTeendo.id", cascade="all, delete-orphan"
    )


class AutoTeendo(TimestampMixin, Base):
    """Egy teendő egy autóhoz (a felhasználó kérése): "vinni műszakira",
    "izzót cserélni", "nyári gumi" - pipálható lista az Autók oldalán,
    járművenként. Szándékosan egyszerű: szöveg + kész-pipa + opcionális
    határidő és felelős."""

    __tablename__ = "auto_teendok"

    id: Mapped[int] = mapped_column(primary_key=True)
    auto_id: Mapped[int] = mapped_column(ForeignKey("autok.id"), nullable=False, index=True)
    szoveg: Mapped[str] = mapped_column(Text, nullable=False)
    kesz: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hatarido: Mapped[date | None] = mapped_column(Date)
    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    auto: Mapped["Auto"] = relationship(back_populates="teendok")
    felelos: Mapped["Employee | None"] = relationship()
