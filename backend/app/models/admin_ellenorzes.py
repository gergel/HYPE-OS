"""ADMINISZTRÁCIÓ ELLENŐRZÉSE (a felhasználó kérése, 2026-10): a tulajdonos
követhesse, mikor mi készült el, mindenhez rendesen van-e papír, és nincs-e
csendben kihagyva semmi - mert az előző kollégánál így elcsúsztak dolgok.

Négy tábla:

- `admin_tevekenysegek`: KI, MIKOR, MIT csinált a papírozásban (szerződés,
  TIG, kiadás, számla...). Csak hozzáfűzhető napló - a rekordokon csak
  létrehozás/módosítás ideje van, felhasználó nincs, ezért kellett.
- `admin_ellenorzes_beallitasok`: egyetlen sor (id=1) - határidők, a figyelt
  kolléga, Lara figyelésének kapcsolója (alapból KI) és a heti áttekintés ideje.
- `admin_kivetel_jelolesek`: a tulajdonos döntése egy-egy kivételről
  (kihagyás, "van már szerződés", számla kihagyva...): rendben / visszadobva.
- `lara_figyeles_jelzesek`: Lara jelzései a figyelt kolléga munkájáról - csak
  az ellenőrző oldalon, csak a tulajdonosnak (lásd services/lara_figyeles.py)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

#: Ettől a naptól nézi az ellenőrzés (a figyelt kolléga ekkor kezdett) -
#: a beállításokban átírható.
ALAP_KEZDET = date(2026, 10, 5)

#: Alapértelmezett határidők (nap) - a beállításokban átírhatók.
ALAP_HATARIDOK = {
    #: A forgatás (utolsó napja) után ennyi nappal már legyen meg a szerződés.
    "szerzodes": 3,
    #: A forgatás után ennyi napon belül menjen ki a TIG.
    "tig": 7,
    #: A forgatás után ennyi napon belül legyen meg a számla.
    "szamla": 30,
    #: A szerződés kiküldése után ennyi napon belül érkezzen vissza aláírva.
    "alairas": 14,
}


class AdminTevekenyseg(Base):
    """Egy papírozási lépés: ki, mikor, mit, min."""

    __tablename__ = "admin_tevekenysegek"
    __table_args__ = (
        Index("ix_admin_tevekenysegek_ki_mikor", "employee_id", "letrejott_at"),
        Index("ix_admin_tevekenysegek_muvelet", "muvelet"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    letrejott_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    #: Gépi kulcs (pl. "kikuldes", "kihagyas", "torles") és a tárgy
    #: ("szerzodes", "tig", "kiadas"...) - a szűréshez és Lara szabályaihoz.
    muvelet: Mapped[str] = mapped_column(String(50), nullable=False)
    targy: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Emberi leírás, pl. "Szerződés: kihagyva".
    leiras: Mapped[str] = mapped_column(String(300), nullable=False)
    #: A kérés módja és útvonal-sablonja (pl. POST /alvallalkozoi-szerzodesek/{project_id}/...).
    metodus: Mapped[str] = mapped_column(String(10), nullable=False)
    utvonal: Mapped[str] = mapped_column(String(300), nullable=False)
    #: Az útvonal paraméterei (project_id, szamlazo_kulcs, contract_id...).
    parameterek: Mapped[dict | None] = mapped_column(JSON)
    project_id: Mapped[int | None] = mapped_column(Integer, index=True)
    #: A beküldött adatokból a lényeg (pl. a kihagyás oka, "nincs számla").
    adat: Mapped[dict | None] = mapped_column(JSON)


class AdminEllenorzesBeallitas(Base):
    """Az ellenőrzés beállításai - egyetlen sor (id=1)."""

    __tablename__ = "admin_ellenorzes_beallitasok"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Kinek a munkáját figyeli Lara (az adminisztrációs kolléga).
    figyelt_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    #: Lara figyelése - új automatizmus, ezért alapból KIKAPCSOLVA.
    lara_figyeles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    #: Határidők napban (lásd ALAP_HATARIDOK).
    hataridok: Mapped[dict | None] = mapped_column(JSON)
    utolso_futas_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Mikor volt az utolsó HETI áttekintés (a felhasználó kérése: Lara hetente
    #: nézze át a kijelölt munkatársat - lásd services/lara_figyeles.py).
    heti_attekintes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Ettől a naptól nézi az ellenőrzés a dolgokat (a felhasználó kérése: a
    #: figyelt kolléga 2026.10.05. óta dolgozik itt - ami előtte volt, az nem
    #: az ő munkája). Üresen az ALAP_KEZDET.
    figyeles_kezdete: Mapped[date | None] = mapped_column(Date)
    modositva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class AdminKivetelJeloles(Base):
    """A tulajdonos döntése egy kivételről (kihagyás és társai)."""

    __tablename__ = "admin_kivetel_jelolesek"
    __table_args__ = (Index("ix_admin_kivetel_jelolesek_kulcs", "kulcs"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A kivétel azonosítója, pl. "szerzodes_kihagyva:123".
    kulcs: Mapped[str] = mapped_column(String(100), nullable=False)
    #: "rendben" vagy "visszadobva".
    dontes: Mapped[str] = mapped_column(String(20), nullable=False)
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    #: Visszadobásnál a kollégának létrehozott feladat.
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    letrejott_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LaraFigyelesJelzes(Base):
    """Lara egy jelzése: valami szokatlan a figyelt kolléga munkájában."""

    __tablename__ = "lara_figyeles_jelzesek"
    __table_args__ = (Index("ix_lara_figyeles_jelzesek_nyitott", "lezarva_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Ugyanarról a dologról csak egy jelzés legyen (pl. "torles:1532").
    kulcs: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    szabaly: Mapped[str] = mapped_column(String(50), nullable=False)
    #: "figyelem" (nézd meg) vagy "info".
    szint: Mapped[str] = mapped_column(String(20), nullable=False, default="figyelem")
    cim: Mapped[str] = mapped_column(String(300), nullable=False)
    leiras: Mapped[str | None] = mapped_column(Text)
    #: Hová vigyen a kattintás (pl. /utokovetes/123).
    link: Mapped[str | None] = mapped_column(String(300))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    adat: Mapped[dict | None] = mapped_column(JSON)
    letrejott_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    #: A tulajdonos lezárta ("láttam / rendben").
    lezarva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lezarta_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
