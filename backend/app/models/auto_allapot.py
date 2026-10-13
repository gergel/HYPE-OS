"""AUTÓ ÁLLAPOTFOTÓK (a felhasználó kérése, 2026-10): az autók állapotáról
fotók készülnek, és autónként visszanézhető, melyik nap milyen kép készült.

Egy alkalommal HÉT kép kell (lásd OLDALAK): a négy oldaláról egy-egy, a
csomagtartó, az első és a hátsó üléssor. A képeket BEKÉRŐ LINKEN töltik fel
(bejelentkezés nélkül, tokennel) - egyelőre csak teszt jelleggel: a linket kézzel
kell kiküldeni, a diszpóval nem megy ki automatikusan.

- `auto_allapot_bekeresek`: egy autó bekérő linkje (visszavonható).
- `auto_allapot_fotok`: egy feltöltött kép - melyik autó, melyik nézet, mikor.
  Egy napon egy nézetből a legutóbbi feltöltés számít (az újrafotózás
  lecseréli az aznapit); más napok képei megmaradnak, így az állapot napról
  napra visszanézhető."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

#: A hét kötelező nézet - (kulcs, felirat), ebben a sorrendben.
OLDALAK: tuple[tuple[str, str], ...] = (
    ("eleje", "Eleje"),
    ("hatulja", "Hátulja"),
    ("bal_oldal", "Bal oldala"),
    ("jobb_oldal", "Jobb oldala"),
    ("csomagtarto", "Csomagtartó"),
    ("elso_ulesek", "Első üléssor"),
    ("hatso_ulesek", "Hátsó üléssor"),
)
OLDAL_KULCSOK = tuple(k for k, _ in OLDALAK)


class AutoAllapotBekeres(Base):
    """Egy autó állapotfotó-bekérő linkje."""

    __tablename__ = "auto_allapot_bekeresek"

    id: Mapped[int] = mapped_column(primary_key=True)
    auto_id: Mapped[int] = mapped_column(ForeignKey("autok.id", ondelete="CASCADE"), nullable=False, index=True)
    #: A link tokenje - nem kitalálható (secrets.token_urlsafe).
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    letrehozta_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    letrejott_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    #: Visszavonás után a link nem él; a vele feltöltött képek megmaradnak.
    visszavonva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fotok: Mapped[list["AutoAllapotFoto"]] = relationship(back_populates="bekeres")


class AutoAllapotFoto(Base):
    """Egy állapotfotó."""

    __tablename__ = "auto_allapot_fotok"

    id: Mapped[int] = mapped_column(primary_key=True)
    auto_id: Mapped[int] = mapped_column(ForeignKey("autok.id", ondelete="CASCADE"), nullable=False, index=True)
    bekeres_id: Mapped[int | None] = mapped_column(
        ForeignKey("auto_allapot_bekeresek.id", ondelete="SET NULL"), index=True
    )
    #: Melyik nézet (lásd OLDALAK).
    oldal: Mapped[str] = mapped_column(String(30), nullable=False)
    #: Mikor töltötték fel - ebből a nap (magyar idő szerint).
    keszult_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    #: Aki a linken megadta a nevét (nem kötelező).
    keszito: Mapped[str | None] = mapped_column(String(120))
    kulcs: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    belyeg_kulcs: Mapped[str | None] = mapped_column(String(500))
    belyeg_url: Mapped[str | None] = mapped_column(String(500))
    meret: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    bekeres: Mapped["AutoAllapotBekeres | None"] = relationship(back_populates="fotok")
