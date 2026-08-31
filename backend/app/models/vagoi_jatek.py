"""Vágói játék - havi pontverseny a vágók között.

Két dologért jár pont, mert ez a kettő a vágói munka két fele:

- **ellenőrzésbe tett anyag**: 50 pont. Ez a "kész lettem vele" pillanata.
- **vágás**: 3 percenként 1 pont. Ez maga a munka.

A hónap végén a legtöbb pontot szerző kapja a hónap elején kihirdetett
nyereményt.

MIÉRT VAN SAJÁT ESEMÉNY-TÁBLA az ellenőrzéshez? Mert a pont a MEGTÖRTÉNT
ESEMÉNYHEZ tartozik, nem az anyag mai állapotához. Ha a pontot abból
számolnánk, hogy most éppen mi az `allapot`, akkor egy későbbi állapotváltás
visszamenőleg elvenné a pontot (az anyag továbbmegy "Kész"-be, és eltűnik a
havi eredményből), egy oda-vissza kattintgatás pedig újra és újra adná. Egy
versenynél mindkettő végzetes: az egyik igazságtalan, a másik játszható.

Az esemény ezért egyszer keletkezik, a `deliverable_id` egyedi - ugyanaz az
anyag akkor sem hoz még egyszer pontot, ha kiveszik és visszateszik.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: Egy ellenőrzésbe tett anyag pontértéke.
ELLENORZES_PONT = 50
#: BÓNUSZ annak, akinek az anyaga az ellenőrzésből JAVÍTÁS NÉLKÜL ment tovább
#: (kiküldésre vár / kész kiküldve) - ez a "elsőre jó lett" jutalma.
JOVAHAGYAS_PONT = 100
#: LEVONÁS annak, akinek az anyaga az ellenőrzésből javításba került.
JAVITAS_PONT = -20
#: Ennyi perc vágás ér egy pontot.
PERC_PER_PONT = 3
#: Ehhez a munkanapszámhoz arányosítunk mindenkit (lásd VagoJatekNap).
ALAP_MUNKANAP = 20


class VagoJatekHonap(TimestampMixin, Base):
    """Egy hónap versenye: mi a nyeremény.

    A nyereményt a hónap ELEJÉN kell kihirdetni - ez a verseny értelme. Ezért
    van saját sora minden hónapnak akkor is, ha még nincs benne pont: a
    felület ebből tudja, hogy van-e már meghirdetett nyeremény, vagy szólni
    kell az adminnak."""

    __tablename__ = "vago_jatek_honapok"
    __table_args__ = (UniqueConstraint("ev", "honap", name="uq_vago_jatek_honap"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ev: Mapped[int] = mapped_column(Integer, nullable=False)
    honap: Mapped[int] = mapped_column(Integer, nullable=False)

    #: Mi a nyeremény ebben a hónapban. Üres = még nincs kihirdetve.
    nyeremeny: Mapped[str | None] = mapped_column(String(255))
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    #: Fotó a nyereményről. Egy kép többet mond, mint a "20 000 Ft utalvány" -
    #: a verseny attól megy, hogy LÁTJÁK, miért mennek.
    #:
    #: A `kep_storage_key` azért van a URL mellett, mert csere/törléskor a régi
    #: objektumot is el kell dobni a tárhelyről - a publikus URL-ből ez nem
    #: mindig fejthető vissza (lásd services/document_storage.py).
    kep_url: Mapped[str | None] = mapped_column(String(500))
    kep_storage_key: Mapped[str | None] = mapped_column(String(500))

    #: A hónap KIHIRDETETT győztese - a hónapváltáskor íródik be, EGYSZER
    #: (lásd services/vagoi_jatek.havi_zaras). Azért tároljuk, és nem számoljuk
    #: mindig újra, mert a kihirdetés után érkező javítások (utólag rögzített
    #: mérés, munkanap-átírás) már nem billenthetik át a végeredményt - egy
    #: kihirdetett győztest nem lehet visszamenőleg leváltani.
    gyoztes_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    #: A győztes pontszáma a kihirdetés pillanatában.
    gyoztes_pont: Mapped[int | None] = mapped_column(Integer)
    #: Mikor történt a kihirdetés. None = a hónap még nem zárult le. Ez hajtja
    #: a dashboard ünneplő widgetét is (a kihirdetéstől 5 napig látszik).
    kihirdetve_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    gyoztes: Mapped["Employee | None"] = relationship()


class VagoJatekNap(TimestampMixin, Base):
    """Hány munkanapja van egy embernek abban a hónapban.

    EZ TESZI IGAZSÁGOSSÁ A VERSENYT. Aki 12 napot dolgozik (mert szabadságon
    volt vagy beteg), az nyers pontban esélytelen azzal szemben, aki 22-t -
    pedig lehet, hogy naponta többet teljesített. Ezért mindenkit úgy
    arányosítunk, mintha ALAP_MUNKANAP (20) napja lett volna:

        arányosított pont = nyers pont x (20 / munkanap)

    Menet közben szerkeszthető: ha valaki megbetegszik vagy plusz napot vállal,
    a szám átírható, és az állás azonnal újraszámolódik - a pontokat nem kell
    hozzányúlni, mert azok a nyers teljesítményt őrzik.

    Akinek nincs sora, az ALAP_MUNKANAP-pal számol, tehát a nyers pontja marad
    - így a beállítás elmaradása senkit nem hoz hátrányba."""

    __tablename__ = "vago_jatek_napok"
    __table_args__ = (UniqueConstraint("ev", "honap", "employee_id", name="uq_vago_jatek_nap"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ev: Mapped[int] = mapped_column(Integer, nullable=False)
    honap: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)

    munkanap: Mapped[int] = mapped_column(Integer, nullable=False, default=ALAP_MUNKANAP)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    employee: Mapped["Employee"] = relationship()


class VagoEllenorzesEsemeny(TimestampMixin, Base):
    """"Ez az anyag ellenőrzésbe került" - egyszer, örökre.

    A `deliverable_id` EGYEDI: ugyanaz az anyag akkor sem hoz még egyszer
    pontot, ha kiveszik az ellenőrzésből és visszateszik. Enélkül a verseny
    egy gombnyomkodó versennyé válna.

    Az `idopont` dönti el, MELYIK hónap versenyébe számít - nem az anyag
    határideje vagy a létrehozása, hanem az, hogy mikor lett kész."""

    __tablename__ = "vago_ellenorzes_esemenyek"
    __table_args__ = (UniqueConstraint("deliverable_id", name="uq_vago_ellenorzes_deliverable"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deliverable_id: Mapped[int] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    #: Ki tette ellenőrzésbe - ő kapja a pontot.
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    idopont: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    #: Melyik állapotba került (a felület ezt írja ki a magyarázatban).
    allapot: Mapped[str | None] = mapped_column(String(50))

    employee: Mapped["Employee"] = relationship()
    deliverable: Mapped["Deliverable"] = relationship()


class VagoEllenorzesKimenet(TimestampMixin, Base):
    """Mi lett az ellenőrzésbe tett anyag SORSA - anyagonként egyszer.

    Az ELSŐ továbblépés dönt: ha az ellenőrzésből javítás nélkül ment tovább
    (kiküldésre vár / kész kiküldve), az +100 pont annak, aki ellenőrzésbe
    tette (JOVAHAGYAS_PONT); ha javításba került, az -20 (JAVITAS_PONT). A
    `deliverable_id` EGYEDI: egy később oda-vissza tologatott anyag nem
    termel és nem is veszít több pontot - az első ítélet számít, mert az
    mondja meg, elsőre jó volt-e.

    Az `idopont` dönti el, melyik hónap versenyébe számít."""

    __tablename__ = "vago_ellenorzes_kimenetek"
    __table_args__ = (UniqueConstraint("deliverable_id", name="uq_vago_ellenorzes_kimenet"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deliverable_id: Mapped[int] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    #: Aki az anyagot ellenőrzésbe tette - ő kapja a bónuszt/levonást.
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    idopont: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    #: "jovahagyva" vagy "javitas".
    kimenet: Mapped[str] = mapped_column(String(20), nullable=False)
    #: A járó pont (+100 / -20) - kiírva tárolva, hogy egy későbbi
    #: szabály-módosítás ne írja át visszamenőleg a régi hónapokat.
    pont: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Melyik állapotba lépett tovább (a felület magyarázatához).
    allapot: Mapped[str | None] = mapped_column(String(50))

    employee: Mapped["Employee"] = relationship()
    deliverable: Mapped["Deliverable"] = relationship()
