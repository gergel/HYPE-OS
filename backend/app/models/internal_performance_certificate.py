from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: Az az állapot-készlet, amiben egy belsős TIG ELKÉSZÜLTNEK számít. A "Kész" a
#: korábbi, küldés nélküli életciklusból maradt: a régi bejegyzések ebben az
#: állapotban vannak, és ugyanúgy lezártnak számítanak, mint az azóta bevezetett
#: "Kiküldve".
LEZART_ALLAPOTOK = frozenset({"Kész", "Kiküldve"})

#: A "nem kell TIG erre a hónapra" állapot (az admin kihagyta, mert a munkatárs
#: akkor nem dolgozott) - ilyenkor nincs mit kifizetni. Itt, a modell mellett
#: van, mert a pénzügyek utalandó listája is használja, a route modulok pedig
#: nem importálnak egymásból.
KIHAGYVA = "Kihagyva"


class InternalPerformanceCertificate(TimestampMixin, Base):
    """Belsős TIG - a PerformanceCertificate (Külsős TIG) párja belsős
    (payroll-on lévő, nem vállalkozói jogviszonyú) munkatársakhoz, de MÁS
    ciklusú: belsősöknek sosem kell projektenként TIG-et készíteni, hanem
    havonta pontosan egyet (lásd api/routes/internal_performance_certificates.py
    - egy admin oldal listázza az adott hónap összes belsős munkatársát,
    alapértelmezetten a folyó hónapra). A (employee_id, ev, honap) hármas
    egyedi - egy embernek egy hónapban csak egy TIG-je lehet.

    Egyszerűbb életciklus, mint a külsősöknél: nincs eseti/keretszerződés-
    előfeltétel. A folyamat: admin rögzíti az összeget és a dátumokat, a
    rendszer generálja a TIG dokumentumot és kiküldi emailben (állapot:
    "Kiküldve"), majd a számla feltöltése után kifizetettként jelölhető, ami
    (a Külsős TIG-hez hasonlóan) létrehoz egy Expense sort - de
    projekthez/projektkódhoz NEM köthető, hiszen a belsős TIG nem egyetlen
    projekt teljesítését igazolja.

    Az (ev, honap) NEM kézzel állított: a teljesites_datuma-ból számoljuk, és
    az MINDIG az azt megelőző hónapot jelenti (2026.06.20-i teljesítés = a
    2026. MÁJUSI TIG) - lásd services/hu_datum.py elozo_honap()."""

    __tablename__ = "internal_performance_certificates"
    __table_args__ = (UniqueConstraint("employee_id", "ev", "honap", name="uq_internal_tig_employee_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    ev: Mapped[int] = mapped_column(nullable=False, comment="Év, pl. 2026")
    honap: Mapped[int] = mapped_column(nullable=False, comment="Hónap, 1-12")

    allapot: Mapped[str | None] = mapped_column(String(50), comment="Belsős TIG állapot")
    megjegyzes: Mapped[str | None] = mapped_column(String(500))
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)

    megbizas_targya: Mapped[str | None] = mapped_column(
        String(255), comment="Alapból a munkatárs adatlapjáról jön, de TIG-enként átírható"
    )
    teljesites_datuma: Mapped[date | None] = mapped_column(
        Date, comment="Ebből jön az igazolt hónap: MINDIG az azt megelőző hónap"
    )
    keltezes: Mapped[date | None] = mapped_column(Date, comment="A dokumentum keltezése")
    file_url: Mapped[str | None] = mapped_column(String(500), comment="A kiküldött TIG dokumentum Drive linkje")
    # Csak akkor van kitöltve, ha a TIG dokumentumot MI tároljuk (kézzel
    # feltöltött vagy Notionból áthozott fájl az R2-n) - a rendszer által
    # generált, Drive-on maradó PDF-nél üres, mert azt nem a mi tárhelyünkről
    # törölnénk.
    file_storage_key: Mapped[str | None] = mapped_column(String(500))

    # A számla két dátuma. Külön a teljesítés/keltezés párostól: azok a TIG
    # DOKUMENTUMÁRÓL szólnak, ez a kettő a pénz útjáról - meddig kell fizetni,
    # és mikor utaltuk el ténylegesen.
    fizetesi_hatarido: Mapped[date | None] = mapped_column(Date, comment="A számla fizetési határideje")
    utalas_datuma: Mapped[date | None] = mapped_column(Date, comment="Mikor utaltuk el ténylegesen")

    szamla_kifizetve: Mapped[bool] = mapped_column(Boolean, default=False)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    employee: Mapped["Employee"] = relationship(back_populates="internal_performance_certificates")
    invoices: Mapped[list["InternalPerformanceCertificateInvoice"]] = relationship(
        back_populates="certificate", cascade="all, delete-orphan", order_by="InternalPerformanceCertificateInvoice.created_at"
    )


class InternalPerformanceCertificateInvoice(TimestampMixin, Base):
    """Egy Belsős TIG-hez feltöltött számla fájl - egy TIG-hez több számla is
    tartozhat (egyenként feltölthető/törölhető), ellentétben a
    szamla_kifizetve/expense_id állapottal, ami a TIG egészére vonatkozik."""

    __tablename__ = "internal_performance_certificate_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    certificate_id: Mapped[int] = mapped_column(
        ForeignKey("internal_performance_certificates.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    # A Notionból átemelt számla forrás-azonosítója (host + útvonal, aláírás
    # nélkül - lásd notion_import/files.forras_kulcs). Ettől idempotens az
    # import: egy újrafuttatás nem tölti le és nem duplikálja ugyanazt a számlát.
    notion_forras: Mapped[str | None] = mapped_column(String(700), index=True)

    certificate: Mapped["InternalPerformanceCertificate"] = relationship(back_populates="invoices")
