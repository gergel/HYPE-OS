from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PerformanceCertificate(TimestampMixin, Base):
    """Teljesítési igazolás (TIG) - eseti, projektenkénti dokumentum minden
    nem belsős stábtaghoz (külsős VAGY keretszerződéses is - a TIG a konkrét
    munka elvégzését igazolja, függetlenül attól, hogy van-e a megbízottnak
    egyébként álló keretszerződése), miután az adott projekten mindenkinek
    megvan a (eseti) szerződése (Contract.szerzodes_allapota "Kiküldve" vagy
    "Kihagyva" mindenkinél, akinek egyáltalán kellett) - lásd
    api/routes/performance_certificates.py. Ugyanaz a kétlépéses (mentés majd
    generálás-és-küldés, vagy kihagyás) életciklus, mint az eseti
    szerződéseknél (Contract), de külön táblában, mert ez egy másik,
    önállóan kezelt dokumentum."""

    __tablename__ = "performance_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A TIG "otthona": az a projekt, ahonnan készült. Egy TIG TÖBB projekt
    #: munkáját is igazolhatja (egy ember egy számlán küld be több forgatást) -
    #: azt a tételek hordozzák, lásd PerformanceCertificateTetel.
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    #: A SZÁMLÁZÓ FÉL, akinek a nevére a TIG szól: vagy egy ember, vagy egy
    #: vállalkozás (pontosan az egyik). Nem feltétlenül az, akinek a munkájáról
    #: szól - egy ember más(ok) munkáját is számlázhatja, lásd
    #: services/szamlazo.py.
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    vallalkozas_id: Mapped[int | None] = mapped_column(ForeignKey("vallalkozasok.id"))

    allapot: Mapped[str | None] = mapped_column(String(50), comment="TIG állapot")
    #: MIÉRT hagytuk ki - a kihagyáskor kötelező megadni. Fél év múlva senki
    #: nem fogja fejből tudni, miért maradt el egy teljesítési igazolás, és a
    #: puszta "Kihagyva" jelölés ilyenkor gyanúsabb, mint amilyen indokolt.
    kihagyas_oka: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(String(500), comment="A TIG dokumentum linkje")
    # Csak akkor van kitöltve, ha a TIG dokumentumot MI tároljuk (a kiküldés
    # helyett feltöltött saját papír az R2-n) - a rendszer által generált,
    # Drive-on maradó dokumentumnál üres, mert azt nem a mi tárhelyünkről
    # törölnénk. Ugyanaz a minta, mint a Belsős TIG-nél.
    file_storage_key: Mapped[str | None] = mapped_column(String(500))

    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(255))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó TIG")
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)
    # A teljesítés ideje SZABAD SZÖVEG, nem dátum: a valóságban nem mindig egy
    # (tól-ig) naptári intervallum kerül a papírra - lehet "2026. július", egy
    # felsorolás, vagy bármilyen megfogalmazás. Ez megy a dokumentum {{tido}}
    # helyére. A régi, dátum-alapú mezők megmaradnak a korábbi bejegyzések
    # miatt (és mert a migráció ezekből töltötte fel a szöveget).
    teljesites_szoveg: Mapped[str | None] = mapped_column(String(255), comment="Teljesítés ideje - szabad szöveg")
    teljesites_kezdete: Mapped[date | None] = mapped_column(Date)
    teljesites_vege: Mapped[date | None] = mapped_column(Date)
    keltezes: Mapped[date | None] = mapped_column(Date, comment="Keltezési idő")
    email: Mapped[str | None] = mapped_column(String(255))

    # Számla feltöltése + kifizetése - a TIG kiküldése után jövő lépés
    # (lásd api/routes/performance_certificates.py /szamla és
    # /szamla-kifizetve végpontjai): a kifizetés automatikusan létrehoz egy
    # Expense sort a megfelelő ProjectCode-hoz kötve, hogy a Pénzügy ->
    # Kiadások összesítőben megjelenjen. Maguk a számlafájlok külön táblában
    # vannak (lásd PerformanceCertificateInvoice), mert egy TIG-hez több
    # számla is tartozhat.
    szamla_kifizetve: Mapped[bool] = mapped_column(Boolean, default=False)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    project: Mapped["Project"] = relationship(back_populates="performance_certificates")
    employee: Mapped["Employee"] = relationship(back_populates="performance_certificates")
    vallalkozas: Mapped["Vallalkozas | None"] = relationship()
    invoices: Mapped[list["PerformanceCertificateInvoice"]] = relationship(
        back_populates="certificate", cascade="all, delete-orphan", order_by="PerformanceCertificateInvoice.created_at"
    )
    tetelek: Mapped[list["PerformanceCertificateTetel"]] = relationship(
        back_populates="certificate", cascade="all, delete-orphan", order_by="PerformanceCertificateTetel.id"
    )


class PerformanceCertificateTetel(TimestampMixin, Base):
    """Egy TIG EGY tétele: kinek a munkáját, melyik projekten igazolja.

    Miért kell? Mert a papír nem mindig egy ember egy projektjéről szól:

    - a projekten két stábtag munkáját ugyanaz a fél számlázza (egy számla,
      egy TIG, két tétel);
    - valaki több lezárt projektjét egyben számlázza (egy TIG, projektenként
      egy tétel).

    Ez ugyanaz a felépítés, mint a belsős havi TIG-nél (egy
    InternalPerformanceCertificate + több EmployeeMonthlyItem, tételenként
    saját projektkóddal) - csak a külsős oldalon.

    A `netto_osszeg` SZÁNDÉKOSAN opcionális: a felhasználó szerint "mikor más
    számláz vagy 4 projektet egybe számláz, akkor nem mindig lehet megmondani,
    hogy mi mennyibe került". A TIG fejösszege (PerformanceCertificate.
    netto_osszeg) az igazság - ez a mező csak akkor tölthető ki, ha a bontás
    ismert. Automatikusan SOSEM osztjuk szét egyenlően: az kitalált számokat
    vinne a projekt-jövedelmezőségbe."""

    __tablename__ = "performance_certificate_tetelek"
    __table_args__ = (
        UniqueConstraint("certificate_id", "project_id", "employee_id", name="uq_tig_tetel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    certificate_id: Mapped[int] = mapped_column(
        ForeignKey("performance_certificates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Melyik projekt melyik emberének a munkája. Egy (projekt, ember) párt
    #: legfeljebb EGY TIG fedhet - erre az adatbázis nem tud kényszert adni
    #: (több TIG-en át kellene néznie), ezért a végpont ellenőrzi
    #: (lásd routes/performance_certificates.py _tetel_utkozes).
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)

    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Ebből ennyi az övé - ha tudható")
    megnevezes: Mapped[str | None] = mapped_column(String(255))

    certificate: Mapped["PerformanceCertificate"] = relationship(back_populates="tetelek")
    #: Két irányban is kell: a TIG-től a projekt felé (a papír szövegéhez), és a
    #: projekt felől a rá szóló tételekhez - a projektkód költsége abból tudja
    #: meg, mennyi külsős munka jut rá akkor is, ha a TIG egy MÁSIK projekt
    #: "otthonában" készült (lásd services/kulsos_koltseg.py).
    project: Mapped["Project"] = relationship(back_populates="tig_tetelek")
    employee: Mapped["Employee"] = relationship()


class PerformanceCertificateInvoice(TimestampMixin, Base):
    """Egy Külsős TIG-hez feltöltött számla fájl - egy TIG-hez több számla is
    tartozhat (egyenként feltölthető/törölhető), ellentétben a
    szamla_kifizetve/expense_id állapottal, ami a TIG egészére vonatkozik.
    Ugyanaz a felépítés, mint a Belsős TIG oldalán
    (InternalPerformanceCertificateInvoice), csak a másik TIG-táblához kötve."""

    __tablename__ = "performance_certificate_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("performance_certificates.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))

    certificate: Mapped["PerformanceCertificate"] = relationship(back_populates="invoices")
