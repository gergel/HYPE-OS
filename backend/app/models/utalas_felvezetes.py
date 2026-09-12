"""UTALÁSOK FELVEZETÉSE - egy MÁR ELUTALT számlacsomag adminisztrálása.

A felhasználó egy ZIP-ben feltölti az elutalt számlákat, megadja az adag közös
utalási dátumát, a rendszer felismeri a számlákat, megkeresi a hozzájuk tartozó
meglévő tételeket (kiadás, külsős/belsős TIG), és EMBERI ELLENŐRZÉS UTÁN
rögzíti a kifizetést. Banki utalást NEM indít - megtörtént utalások
könyveléséről szól.

Fontos üzleti szabály: a számla vevője jellemzően HYPE akkor is, ha a költség
belső elszámolása a Krumpellóhoz tartozik - a vevő neve ezért NEM dönti el az
elszámolási helyet, azt tételenként (vagy kijelöltekre tömegesen) kell
megválasztani. A Krumpellóhoz sorolt tételekhez (a felhasználó kérése) egyelőre
SEMMILYEN rögzítés nem történik: csak listázzuk őket, a kezelésük később
készül el."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: Az adag állapotai: a feldolgozás háttérben fut, utána ellenőrzés jön.
ADAG_ALLAPOTOK = ("feldolgozas", "ellenorzes", "hiba")

#: A tétel érthető állapotai (a felhasználó előírása szerint):
TETEL_ALLAPOTOK = {
    "feldolgozas": "Feldolgozás alatt",
    "rogzitheto": "Rögzíthető",
    "valasztas": "Választás szükséges",
    "nincs_talalat": "Nincs megtalált tétel",
    "mar_kifizetve": "Már kifizetve",
    "osszeg_elter": "Eltérő összeg / részfizetés",
    "duplikatum": "Duplikátum",
    "nem_feldolgozhato": "Nem feldolgozható",
    "rogzitve": "Rögzítve",
}

ELSZAMOLASOK = ("hype", "krumpello", "tisztazando")

#: A tétel célja a rögzítéskor.
CEL_TIPUSOK = ("kiadas", "kulsos_tig", "belsos_tig", "uj_kiadas")


class UtalasAdag(TimestampMixin, Base):
    """Egy feltöltött ZIP-csomag = egy adag, a KÖZÖS utalási dátummal.

    Tartósan mentett: bezárás vagy megszakadt kapcsolat után a lista oldalról
    újranyitható és folytatható."""

    __tablename__ = "utalas_adagok"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str | None] = mapped_column(String(200))
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    #: A TÉNYLEGES banki utalás napja (nem a számla kelte/teljesítése/
    #: határideje és nem a feltöltés napja) - kötelező, alapérték nincs.
    utalas_datum: Mapped[date] = mapped_column(Date, nullable=False)

    zip_fajl_nev: Mapped[str | None] = mapped_column(String(255))
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="feldolgozas")
    hiba_uzenet: Mapped[str | None] = mapped_column(Text)
    #: Hány ÉRDEMI fájl volt a ZIP-ben (a technikai/kihagyott fájlok nélkül).
    fajl_darab: Mapped[int] = mapped_column(nullable=False, default=0)
    #: A kihagyott fájlok jegyzéke: [{"nev", "ok"}] - látszódjon, mi maradt ki.
    kihagyott_fajlok: Mapped[dict | list | None] = mapped_column(JSON)

    letrehozo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    letrehozo = relationship("Employee", foreign_keys=[letrehozo_employee_id])

    tetelek: Mapped[list["UtalasTetel"]] = relationship(
        back_populates="adag", cascade="all, delete-orphan", order_by="UtalasTetel.id"
    )


class UtalasTetel(TimestampMixin, Base):
    """Egy fájl (számla) az adagból - a kinyert adatokkal, a megtalált céllal
    és a rögzítés naplójával."""

    __tablename__ = "utalas_tetelek"

    id: Mapped[int] = mapped_column(primary_key=True)
    adag_id: Mapped[int] = mapped_column(ForeignKey("utalas_adagok.id", ondelete="CASCADE"), index=True)

    # ── A fájl ──────────────────────────────────────────────────────────────
    fajl_nev: Mapped[str | None] = mapped_column(String(255))
    #: A ZIP-en belüli teljes útvonal (almappákkal) - az eredet őrzése.
    fajl_utvonal: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(100))
    meret_bajt: Mapped[int | None] = mapped_column()
    fajl_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(500))

    # ── Kinyert számlaadatok (kereshető oszlopok + teljes JSON) ─────────────
    kinyert: Mapped[dict | list | None] = mapped_column(JSON)
    dokumentum_tipus: Mapped[str | None] = mapped_column(String(30))
    szamlaszam: Mapped[str | None] = mapped_column(String(100), index=True)
    kibocsato_nev: Mapped[str | None] = mapped_column(String(300))
    kibocsato_adoszam: Mapped[str | None] = mapped_column(String(50))
    vevo_nev: Mapped[str | None] = mapped_column(String(300))
    netto: Mapped[float | None] = mapped_column(Numeric(14, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(14, 2))
    penznem: Mapped[str] = mapped_column(String(10), nullable=False, default="HUF")
    kiallitas_datuma: Mapped[date | None] = mapped_column(Date)
    teljesites_datuma: Mapped[date | None] = mapped_column(Date)
    fizetesi_hatarido: Mapped[date | None] = mapped_column(Date)

    # ── Állapot + elszámolás ────────────────────────────────────────────────
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="feldolgozas")
    hiba_uzenet: Mapped[str | None] = mapped_column(Text)
    #: HYPE / Krumpello / Tisztázandó - a számla VEVŐJÉT nem írja át.
    elszamolas: Mapped[str] = mapped_column(String(20), nullable=False, default="tisztazando")

    # ── A megtalált / kiválasztott cél ──────────────────────────────────────
    cel_tipus: Mapped[str | None] = mapped_column(String(30))
    cel_expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"))
    cel_certificate_id: Mapped[int | None] = mapped_column(
        ForeignKey("performance_certificates.id", ondelete="SET NULL")
    )
    cel_internal_certificate_id: Mapped[int | None] = mapped_column(
        ForeignKey("internal_performance_certificates.id", ondelete="SET NULL")
    )
    #: Új kiadás ELŐKÉSZÍTETT adatai (project_code_id, employee_id, auto_id,
    #: tipus, kiadas_leiras, arfolyam...) - kiadás CSAK jóváhagyáskor születik.
    uj_kiadas: Mapped[dict | list | None] = mapped_column(JSON)
    #: A párosítás javaslata: {indoklas, alternativak, figyelmeztetesek}.
    javaslat: Mapped[dict | list | None] = mapped_column(JSON)

    #: Tételi eltérő utalási dátum - NULL = az adag közös dátuma érvényes.
    utalas_datum: Mapped[date | None] = mapped_column(Date)
    #: A felhasználó kifejezetten elfogadta az összeg-eltérést (részfizetésnél
    #: NEM zárjuk le a kötelezettséget e nélkül).
    osszeg_elteres_elfogadva: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    duplikatum_tetel_id: Mapped[int | None] = mapped_column(ForeignKey("utalas_tetelek.id", ondelete="SET NULL"))

    # ── Rögzítés + visszavonás (napló) ──────────────────────────────────────
    rogzitve_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rogzito_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    #: {datum, elozo_ertekek, letrejott, csatolt, megjegyzesek} - a visszavonás
    #: KIZÁRÓLAG ebből dolgozik (bizonyítható eredet, találgatás nincs).
    rogzites_naplo: Mapped[dict | list | None] = mapped_column(JSON)
    visszavonva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visszavono_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))

    adag: Mapped[UtalasAdag] = relationship(back_populates="tetelek")
    rogzito = relationship("Employee", foreign_keys=[rogzito_employee_id])
