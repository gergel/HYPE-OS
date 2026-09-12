"""BEÉRKEZŐ SZÁMLÁK - a számla-érkeztetés piszkozatai (a felhasználó kérése).

A cél: a számla e-mailben megérkezik (szamla@hypestab.hu) vagy az AI
Assistantba bedobva érkezik, a rendszer kiolvassa, megkeresi a helyét
(meglévő TIG, kiadás, E-Rezsi előfizetés, autó, projektkód…), és egy TARTÓSAN
MENTETT, újranyitható PISZKOZATOT készít - a felhasználónak csak ellenőriznie
és jóváhagynia kell. A tényleges pénzügyi rekord (kiadás, TIG-számla sor)
KIZÁRÓLAG a jóváhagyáskor jön létre: a piszkozat önmagában semmilyen éles
költség-, profit-, kassza- vagy utalási összesítést nem érint.

NÉGY KÜLÖN ÁLLAPOT, amit szándékosan nem mosunk össze:
- a FELDOLGOZÁS állapota (`allapot`): hol tart a piszkozat;
- az ELLENŐRZÉS/JÓVÁHAGYÁS: ki és mikor hagyta jóvá (`jovahagyo_employee_id`);
- a számla KIFIZETÉSE: az a létrejövő kiadás/TIG dolga - egy jóváhagyott
  számla NEM kifizetett (a kiadás kesz=False-szal születik);
- a projekt FEDEZETE: azt a meglévő utalás-nézetek számolják, ez a tábla
  hozzájuk nem nyúl.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: A piszkozat feldolgozási állapotai.
ALLAPOT_FELDOLGOZAS = "feldolgozas"
ALLAPOT_ELLENORZENDO = "ellenorzendo"
ALLAPOT_PONTOSITAS = "pontositas"
ALLAPOT_JOVAHAGYVA = "jovahagyva"
ALLAPOT_DUPLIKATUM = "duplikatum"
ALLAPOT_NEM_SZAMLA = "nem_szamla"
ALLAPOT_HIBA = "hiba"

ALLAPOTOK = (
    ALLAPOT_FELDOLGOZAS,
    ALLAPOT_ELLENORZENDO,
    ALLAPOT_PONTOSITAS,
    ALLAPOT_JOVAHAGYVA,
    ALLAPOT_DUPLIKATUM,
    ALLAPOT_NEM_SZAMLA,
    ALLAPOT_HIBA,
)

#: Hová készül a rögzítés (a jóváhagyás célja). A "kiadas_uj" új kiadást hoz
#: létre; a többi MEGLÉVŐ rekordhoz csatol/egészít ki - új személyi költséget
#: sosem duplikál.
CEL_TIPUSOK = (
    "kiadas_uj",          # új egyéb/projekt-kiadás (kesz=False, nem kifizetett)
    "kiadas_csatolas",    # meglévő kiadáshoz hiányzó számla csatolása
    "kulsos_tig",         # meglévő külsős TIG számlája
    "belsos_tig",         # meglévő havi belsős TIG számlája
    "erezsi",             # E-Rezsi előfizetés adott időszaki számlája
    "auto",               # autóhoz tartozó költség (új kiadás auto_id-val)
    "kp",                 # meglévő KP-tétel bizonylat-pótlása
    "mukodesi",           # tudatosan projekt nélküli általános működési költség
    "kimeno",             # kimenő/megrendelői számla - NEM rögzíthető kiadásként
    "egyeb",              # tisztázandó / nem támogatott
)


class BejovoSzamla(TimestampMixin, Base):
    """Egy beérkezett számla-dokumentum piszkozata - a teljes életúttal.

    A kinyert adatok kettős könyvelése szándékos: a gyakran keresett mezők
    (kibocsátó, számlaszám, összegek, dátumok) OSZLOPOKBAN állnak (lista,
    szűrés, duplikáció-vizsgálat), a TELJES kinyert kép pedig - mezőnkénti
    forrással és a bizonytalan mezők listájával - a `kinyert` JSON-ban."""

    __tablename__ = "bejovo_szamlak"

    id: Mapped[int] = mapped_column(primary_key=True)

    #: Honnan érkezett: "email" | "asszisztens" | "kezi".
    forras: Mapped[str] = mapped_column(String(20), nullable=False, default="kezi")
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default=ALLAPOT_FELDOLGOZAS, index=True)
    hiba_uzenet: Mapped[str | None] = mapped_column(Text)

    # ── Az eredeti dokumentum ────────────────────────────────────────────────
    fajl_nev: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(100))
    meret_bajt: Mapped[int | None] = mapped_column()
    #: A fájl SHA-256 lenyomata - az azonos tartalom (más néven újra beküldve
    #: is) erről ismerszik meg. NULL: fájl nélküli piszkozat (pl. csak
    #: letöltő-linkes levél).
    fajl_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    #: UGYANAZON számla MÁSIK formátuma (pl. a PDF melletti XML): a változat a
    #: fő piszkozathoz kapcsolódik, nem külön számla.
    valtozat_szamla_id: Mapped[int | None] = mapped_column(
        ForeignKey("bejovo_szamlak.id", ondelete="SET NULL"), index=True
    )

    # ── E-mail metaadatok (csak email-forrásnál) ────────────────────────────
    #: A Gmail üzenet-azonosító - az újraküldés/újraindulás elleni védelem
    #: kulcsa (lásd BejovoEmail).
    email_uzenet_id: Mapped[str | None] = mapped_column(String(300), index=True)
    email_felado: Mapped[str | None] = mapped_column(String(300))
    email_targy: Mapped[str | None] = mapped_column(String(500))
    email_beerkezes: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: A levél szövege RÖVIDÍTVE - a besoroláshoz kell ("a HYPE26-0291-hez
    #: küldöm"), nem archívumnak: az eredeti levél a postafiókban marad.
    email_szoveg: Mapped[str | None] = mapped_column(Text)

    # ── Kinyert számlaadatok (a gyakran keresett mezők oszlopként) ──────────
    #: szamla | elolegszamla | vegszamla | modosito | storno | dijbekero | egyeb
    dokumentum_tipus: Mapped[str | None] = mapped_column(String(30))
    szamlaszam: Mapped[str | None] = mapped_column(String(100), index=True)
    kibocsato_nev: Mapped[str | None] = mapped_column(String(300))
    kibocsato_adoszam: Mapped[str | None] = mapped_column(String(50))
    vevo_nev: Mapped[str | None] = mapped_column(String(300))
    vevo_adoszam: Mapped[str | None] = mapped_column(String(50))
    kiallitas_datuma: Mapped[date | None] = mapped_column(Date)
    teljesites_datuma: Mapped[date | None] = mapped_column(Date)
    fizetesi_hatarido: Mapped[date | None] = mapped_column(Date)
    #: Az EREDETI, a számlán szereplő összegek, a számla SAJÁT pénznemében -
    #: a forintérték (ha kell) a jóváhagyáskor, a meglévő deviza-logika
    #: szerint keletkezik (lásd services/penznem.py), itt nem számolunk át.
    netto: Mapped[float | None] = mapped_column(Numeric(14, 2))
    afa_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(14, 2))
    penznem: Mapped[str] = mapped_column(String(3), nullable=False, default="HUF")
    #: bejovo | kimeno | ismeretlen - a számlán szereplő felek alapján (a mi
    #: cégünk vevő vagy kibocsátó), SOSEM az e-mail irányából.
    irany: Mapped[str | None] = mapped_column(String(15))

    #: A TELJES kinyert kép: {"mezok": {...}, "mezo_forrasok": {mező:
    #: "dokumentum"|"email"|"felhasznalo"|"rendszer"}, "bizonytalan": [mező…],
    #: "tetelek": […], "afa_kulcsok": […], "hivatkozasok": {...}} - az
    #: ellenőrző felület ebből mutatja, mi honnan származik.
    kinyert: Mapped[dict | None] = mapped_column(JSON)

    # ── Besorolási javaslat és a felhasználó szava ──────────────────────────
    #: {"tipus": CEL_TIPUSOK egyike, "indoklas": "...", "alternativak":
    #: [{"tipus", "cimke", "cel_id", "indoklas"}...], "figyelmeztetesek": […]}
    javaslat: Mapped[dict | None] = mapped_column(JSON)
    #: A felhasználó kifejezett utasítása (chatből vagy az ellenőrzőből) -
    #: a besorolás első számú forrása, de jogosultságot és ellentmondó
    #: számlaadatot nem írhat felül némán.
    felhasznaloi_utasitas: Mapped[str | None] = mapped_column(Text)

    #: A KIVÁLASZTOTT cél (lásd CEL_TIPUSOK) és a VALÓDI rekord-kapcsolatok.
    cel_tipus: Mapped[str | None] = mapped_column(String(30))
    cel_project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id", ondelete="SET NULL"))
    cel_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    cel_expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"))
    cel_certificate_id: Mapped[int | None] = mapped_column(
        ForeignKey("performance_certificates.id", ondelete="SET NULL")
    )
    cel_internal_certificate_id: Mapped[int | None] = mapped_column(
        ForeignKey("internal_performance_certificates.id", ondelete="SET NULL")
    )
    cel_kotelezettseg_idoszak_id: Mapped[int | None] = mapped_column(
        ForeignKey("kotelezettseg_idoszakok.id", ondelete="SET NULL")
    )
    cel_auto_id: Mapped[int | None] = mapped_column(ForeignKey("autok.id", ondelete="SET NULL"))
    cel_kp_forgalom_id: Mapped[int | None] = mapped_column(ForeignKey("kp_forgalmak.id", ondelete="SET NULL"))
    #: A számlázó fél (alvállalkozó), ha a kiadás emberhez kötött.
    cel_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))

    # ── Jóváhagyás és audit ──────────────────────────────────────────────────
    letrehozo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    jovahagyo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    jovahagyva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: A jóváhagyás EREDMÉNYE: ha új kiadás született (vagy meglévőhöz
    #: csatoltunk), melyik - erről nyílik a link a rögzített tételre.
    rogzitett_expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"))
    #: Mi történt pontosan a jóváhagyáskor (napló): létrehozott/érintett
    #: rekordok típusa+id-je, felosztás, megjegyzések.
    rogzites_naplo: Mapped[dict | None] = mapped_column(JSON)
    #: Duplikátumnál: melyik KORÁBBI piszkozat/rögzítés miatt.
    duplikatum_bejovo_id: Mapped[int | None] = mapped_column(
        ForeignKey("bejovo_szamlak.id", ondelete="SET NULL")
    )
    duplikatum_megjegyzes: Mapped[str | None] = mapped_column(Text)

    letrehozo = relationship("Employee", foreign_keys=[letrehozo_employee_id])
    jovahagyo = relationship("Employee", foreign_keys=[jovahagyo_employee_id])


class BejovoEmail(TimestampMixin, Base):
    """A MÁR FELDOLGOZOTT levelek nyilvántartása - az idempotencia kulcsa.

    A Gmail-lehúzás nem az olvasott/olvasatlan jelzőn múlik: minden látott
    üzenet ide kerül a Gmail-azonosítójával, és ami itt van, azt másodszor nem
    dolgozzuk fel - újraindulás, újraküldés vagy ismételt lehúzás után sem.
    Az eredeti levélhez nem nyúlunk (nem törlünk, nem válaszolunk)."""

    __tablename__ = "bejovo_emailek"
    __table_args__ = (UniqueConstraint("gmail_uzenet_id", name="uq_bejovo_email_uzenet"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_uzenet_id: Mapped[str] = mapped_column(String(300), nullable=False)
    felado: Mapped[str | None] = mapped_column(String(300))
    targy: Mapped[str | None] = mapped_column(String(500))
    beerkezes: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: "feldolgozva" | "nincs_csatolmany" (linkes/üres levél - kézi teendő) |
    #: "kihagyva" (nem számla-jellegű) | "hiba"
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="feldolgozva")
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    letrehozott_szamla_db: Mapped[int] = mapped_column(nullable=False, default=0)
