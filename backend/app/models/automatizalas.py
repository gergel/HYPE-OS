"""Automatizálási audit-napló és az utókövetési emlékeztető-mátrix.

Két, egymástól független tábla, de ugyanaz a fejlesztés hozta őket (a
strukturált számla-piszkozat és a hiányzó alvállalkozói dokumentumok
utókövetése, lásd services/szamla_draft.py és services/utokovetes_hianyok.py):

- `automatizalas_audit`: MINDEN automatikus művelet és gépi (AI / szabály)
  által javasolt adategyeztetés nyoma. Csak hozzáfűzhető: nincs rá módosító
  vagy törlő végpont, és a kód sem ír bele utólag.
- `utokovetes_dokumentumok`: az utókövetési mátrix (projekt × számlázó fél ×
  dokumentum) TÁROLT része - hány emlékeztető ment ki, mikor volt az utolsó
  értesítés. A dokumentum ÉLŐ állapotát nem itt tartjuk (azt mindig a
  szerződés/TIG/számla sorokból számoljuk), csak azt, hogy az utolsó
  emlékeztető idején mi volt - így látszik, változott-e azóta."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

#: Ki végezte a műveletet: a rendszer magától (ütemezett / beérkezéskor),
#: egy gépi javaslattevő (AI-kiolvasás, Lara), vagy egy ember.
SZEREPLOK = ("rendszer", "ai", "felhasznalo")

#: A mátrix dokumentum-fajtái.
DOKUMENTUM_TIPUSOK = ("szerzodes", "tig", "szamla")


class AutomatizalasAudit(Base):
    """Egy automatikus művelet vagy gépi adategyeztetés naplósora."""

    __tablename__ = "automatizalas_audit"
    __table_args__ = (Index("ix_automatizalas_audit_eroforras", "eroforras_tipus", "eroforras_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tortent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    szereplo: Mapped[str] = mapped_column(String(20), nullable=False)
    #: A műveletet indító vagy megerősítő ember (ha volt).
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    #: Pl. "szamla_draft.letrehozas", "szamla_draft.validacio",
    #: "szamla.jovahagyas", "szamla.automatikus_besorolas",
    #: "utokovetes.emlekezteto".
    muvelet: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    eroforras_tipus: Mapped[str] = mapped_column(String(40), nullable=False)
    eroforras_id: Mapped[int | None] = mapped_column(Integer)
    #: "ok" | "elutasitva" | "hiba"
    eredmeny: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    #: Mi volt a bemenet, mit javasolt a gép, mi lett a döntés. Titok és
    #: személyes adat (bankszámlaszám, e-mail törzs) NEM kerülhet ide.
    reszletek: Mapped[dict | None] = mapped_column(JSON)


class UtokovetesDokumentum(TimestampMixin, Base):
    """Az utókövetési mátrix egy cellájának TÁROLT része: egy projekten egy
    számlázó fél egy dokumentumáról kiküldött emlékeztetők."""

    __tablename__ = "utokovetes_dokumentumok"
    __table_args__ = (
        UniqueConstraint("project_id", "szamlazo_kulcs", "dokumentum_tipus", name="uq_utokovetes_dokumentum"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    #: "e12" (ember) vagy "v3" (vállalkozás) - lásd services/szamlazo.py.
    szamlazo_kulcs: Mapped[str] = mapped_column(String(20), nullable=False)
    dokumentum_tipus: Mapped[str] = mapped_column(String(20), nullable=False)
    emlekezteto_db: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    utolso_ertesites_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: "email" | "telefon" | "szemelyes" | "egyeb"
    utolso_ertesites_csatorna: Mapped[str | None] = mapped_column(String(20))
    utolso_ertesites_megjegyzes: Mapped[str | None] = mapped_column(Text)
    #: A dokumentum állapota az utolsó emlékeztető PILLANATÁBAN.
    allapot_ertesiteskor: Mapped[str | None] = mapped_column(String(30))
    utolso_ertesito_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
