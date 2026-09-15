"""AI ASSISTANT - tartós beszélgetések, események és művelet-napló.

A cél (a felhasználó kérése): az asszisztens ne csak kérdésekre válaszoljon,
hanem a rendszer TÉNYLEGES műveleteit végezze el természetes nyelvű kérésre -
ehhez pedig a beszélgetésnek, a végrehajtott műveleteknek és a függő
jóváhagyásoknak TARTÓSNAK kell lenniük, nem csak a modell memóriájában
létezniük: oldalfrissítés után a valós állapot visszaáll, a napló
visszakereshető, az ismételt végrehajtás ellen az idempotencia-kulcs véd.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class AiBeszelgetes(TimestampMixin, Base):
    """Egy felhasználó egy beszélgetés-szála az asszisztenssel."""

    __tablename__ = "ai_beszelgetesek"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    #: Az első üzenetből képzett rövid cím - a beszélgetés-lista ezt mutatja.
    cim: Mapped[str | None] = mapped_column(String(200))
    #: Fut-e éppen egy asszisztens-kör - a felület ebből tudja, hogy pollozzon,
    #: és hogy a "folytatom a munkát" állítás igaz-e (csak tényleg futó körről
    #: állítjuk). Az kör végén mindig False-ra áll (hibánál is).
    fut: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: A felhasználó leállítást kért - a futó kör a következő lépés előtt
    #: megáll, és jelzi, meddig jutott.
    leallitas_kert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    employee = relationship("Employee")


class AiUzenet(TimestampMixin, Base):
    """A beszélgetés egy bejegyzése.

    szerep:
    - "felhasznalo": a felhasználó üzenete (a csatolt fájlok nevével);
    - "asszisztens": a modell végső válasza;
    - "esemeny": folyamat-lépés ("Megkerestem a projektet…"), kártya vagy
      megerősítés-kérés - az `adat` JSON mondja meg, mit rajzoljon a felület.
    """

    __tablename__ = "ai_uzenetek"

    id: Mapped[int] = mapped_column(primary_key=True)
    beszelgetes_id: Mapped[int] = mapped_column(ForeignKey("ai_beszelgetesek.id", ondelete="CASCADE"), index=True)
    szerep: Mapped[str] = mapped_column(String(20), nullable=False)
    szoveg: Mapped[str | None] = mapped_column(Text)
    #: {"tipus": "lepes" | "megerosites" | "bejovo_szamla" | "hiba" | ...,
    #:  további típusfüggő mezők (muvelet_id, bejovo_id, hivatkozasok…)}
    adat: Mapped[dict | None] = mapped_column(JSON)


class AiFajl(TimestampMixin, Base):
    """A beszélgetéshez csatolt fájl - a tárhelyen (R2), nem a lemezen.

    A fájl önmagában csak a beszélgetéshez tartozik; az eszközök (számla-
    érkeztetés, dokumentum-csatolás) innen olvassák fel, és a `felhasznalva`
    naplózza, hova került."""

    __tablename__ = "ai_fajlok"

    id: Mapped[int] = mapped_column(primary_key=True)
    beszelgetes_id: Mapped[int] = mapped_column(ForeignKey("ai_beszelgetesek.id", ondelete="CASCADE"), index=True)
    fajl_nev: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    meret_bajt: Mapped[int | None] = mapped_column()
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    #: [{"mint": "bejovo_szamla"|"attachment", "id": ..., "mikor": ...}]
    felhasznalva: Mapped[list | None] = mapped_column(JSON)


class AiMuvelet(TimestampMixin, Base):
    """Egy ÍRÓ művelet naplója és (szükség esetén) függő jóváhagyása.

    Minden írás ide kerül: ki kezdeményezte, mit hívott, mi lett az eredmény.
    A megerősítendő műveletek "fuggo" állapotban várnak - a végrehajtás CSAK a
    felhasználó felületi jóváhagyása után, PONTOSAN a tárolt kéréssel történik
    (a modell nem tudja utólag átírni). Az idempotencia-kulcs a kettős
    végrehajtás ellen véd: ugyanazzal a kulccsal érkező ismétlés a tárolt
    eredményt kapja vissza, nem fut le újra."""

    __tablename__ = "ai_muveletek"
    __table_args__ = (UniqueConstraint("beszelgetes_id", "idempotencia_kulcs", name="uq_ai_muvelet_idem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    beszelgetes_id: Mapped[int] = mapped_column(ForeignKey("ai_beszelgetesek.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    idempotencia_kulcs: Mapped[str | None] = mapped_column(String(120))
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    keres: Mapped[dict | list | None] = mapped_column(JSON)
    #: Emberi összefoglaló a megerősítés-kártyához ("A 2. utómunka határidejét
    #: szeptember 22-re állítom").
    osszefoglalo: Mapped[str | None] = mapped_column(Text)
    #: fuggo | vegrehajtva | elutasitva | hiba
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="fuggo", index=True)
    valasz_status: Mapped[int | None] = mapped_column()
    valasz: Mapped[dict | list | None] = mapped_column(JSON)
    vegrehajtva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
