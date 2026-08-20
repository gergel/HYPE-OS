from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Expense(TimestampMixin, Base):
    """Kiadás - Kiadások + Projekt kiadások + Belsős extra kiadások egyesítve."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    megnevezes: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    #: Melyik céges autóra ment a költség (tankolás, szerviz, matrica). Az autó
    #: oldala ezeket a sorokat mutatja - de a kiadás ettől ugyanúgy szerepel a
    #: Pénzügy összesítő kiadásai közt, mert EZ az a rekord, nem egy másolata
    #: (lásd models/auto.py).
    auto_id: Mapped[int | None] = mapped_column(ForeignKey("autok.id"), index=True)

    tipus: Mapped[str | None] = mapped_column(String(50), comment="belsos / kulsos / extra")
    netto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    kifizetes_modja: Mapped[str | None] = mapped_column(String(50))
    fizetes_hatarideje: Mapped[date | None] = mapped_column(Date)
    kesz: Mapped[bool] = mapped_column(Boolean, default=False)

    # a 'Kiadások' / 'Projekt kiadások' / 'Belsős extra kiadások' Notion táblák maradék mezői
    letrehozta_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Created by")
    afa_osszege: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="ÁFÁ összege")
    szamla: Mapped[str | None] = mapped_column(String(255))
    kiadas_megnevezese_projekt_kod: Mapped[str | None] = mapped_column(String(255), comment="Kiadás megnevezése/Project kód")
    netto_forintban_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó forintban")
    fizetes_datuma: Mapped[date | None] = mapped_column(Date)
    mikor_fizetett: Mapped[str | None] = mapped_column(String(120))
    szamla_pdf_urls: Mapped[dict | list | None] = mapped_column(JSON, comment="Számla pdf")
    plusz_afa: Mapped[str | None] = mapped_column(String(50), comment="+ÁFA")
    hozzaadas_a_kiadasokhoz: Mapped[bool | None] = mapped_column(Boolean, comment="Hozzá adás a kiadásokhoz")
    forintban_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Forintban")
    kiadas_datuma: Mapped[date | None] = mapped_column(Date)
    projekt_kiadasok_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Projekt kiadások")
    kiadasok_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Kiadások")
    szamla_statusza: Mapped[str | None] = mapped_column(String(50))
    fedezes: Mapped[str | None] = mapped_column(String(50))
    osszes_kiadas_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Összes kiadás")
    tulora_osszege: Mapped[float | None] = mapped_column(Numeric(12, 2))
    plusz_afa_mezo: Mapped[str | None] = mapped_column(String(50), comment="Plusz Áfa")
    arfolyam: Mapped[float | None] = mapped_column(Numeric(10, 4))
    datum_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Dátum")
    projektkod_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Projektkód")
    egyeb_kiadas: Mapped[dict | list | None] = mapped_column(JSON, comment="Egyéb kiadás")
    tulora_orabere: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Túlóra órabér")
    tulora_szama: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="Túlóra száma")
    egyeni_afa_osszege: Mapped[float | None] = mapped_column(Numeric(12, 2))
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    plusz_napok_ara: Mapped[float | None] = mapped_column(Numeric(12, 2))
    plusz_napok_szama: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # ── Devizás felvezetés (lásd services/penznem.py) ───────────────────────
    #
    # A `netto`/`brutto` MINDIG forint, a `penznem` ezért "HUF". Ha a tételt
    # euróban vagy dollárban vezették fel, itt marad meg, HOGYAN: enélkül egy
    # 592 500 Ft-os sor mögött fél év múlva senki nem tudná, hogy az 1 500 EUR
    # volt 395-ös árfolyamon - pedig a számlán az áll.
    eredeti_penznem: Mapped[str | None] = mapped_column(
        String(10), comment="Milyen pénznemben vezették fel (NULL = forintban)"
    )
    eredeti_netto: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="A nettó az eredeti pénznemben")
    eredeti_brutto: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="A bruttó az eredeti pénznemben")

    project_code: Mapped["ProjectCode"] = relationship(back_populates="expenses")
    employee: Mapped["Employee"] = relationship(back_populates="expenses")
    auto: Mapped["Auto | None"] = relationship(back_populates="kiadasok")
    kp_forgalmak: Mapped[list["KpForgalom"]] = relationship(back_populates="expense")


class Revenue(TimestampMixin, Base):
    """Bevétel - egy Project Code-hoz kötve."""

    __tablename__ = "revenues"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False)

    bevetel_formaja: Mapped[str | None] = mapped_column(String(50))
    #: Beleszámít-e az ÉVES bevételbe? A kiadás-oldali
    #: `hozzaadas_a_kiadasokhoz` párja, ugyanazzal a szabállyal: NULL =
    #: beleszámít. Így a régi (Notionból importált) sorok nem tűnnek el némán
    #: az összesítőkből egy új mező bevezetése miatt.
    #:
    #: Hamisra akkor áll, ha a munka ki van fizetve, de a pénz NEM ezen az
    #: úton jött (beszámítás, csere, másik cégen át rendezve) - ilyenkor a sor
    #: attól még LÁTSZIK a bevétel-listán és a projekt profitjában, csak az
    #: éves bevételbe nem számít, mert ott duplázna vagy hazudna.
    #: Lásd services/elszamolas.bevetel_beleszamit.
    beleszamit_a_bevetelekbe: Mapped[bool | None] = mapped_column(
        Boolean, comment="Beleszámít-e az éves bevételbe (NULL = igen)"
    )
    netto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    brutto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    #: HOGYAN jött be a pénz: készpénz vagy átutalás. A készpénzes tételekből
    #: áll össze a kassza egyenlege (lásd services/fizetesi_mod.py) - a kiadás
    #: oldali `kifizetes_modja` párja.
    fizetes_modja: Mapped[str | None] = mapped_column(
        String(50), comment="Készpénz / Átutalás - ebből számol a kassza"
    )
    fizetes_hatarideje: Mapped[date | None] = mapped_column(Date)
    fizetes_datuma: Mapped[date | None] = mapped_column(Date)
    # A megrendelői számla köztes állapota - a számla NEM ebben a rendszerben
    # készül (külső számlázási rendszerben állítják ki), itt csak azt
    # rögzítjük, mikor lett kiállítva/kiküldve a megrendelőnek. Amíg ez None,
    # a bevétel "nincs kiállítva" állapotú; utána "számla kiállítva, még nem
    # fizetve"; a fizetes_datuma kitöltése zárja "kifizetve"-re (lásd spec
    # 3.3/5.3 - a régi rendszerben a fizetés-dátum önmagában bináris volt,
    # nem különböztette meg a "még ki sem lett állítva" és "kiállítva, de még
    # nem fizetve" eseteket).
    szamla_kiallitva_datuma: Mapped[date | None] = mapped_column(Date, comment="Számla kiállítva dátuma")

    # A KIMENŐ (megrendelői) számla feltöltött fájlja. Maga a számla külső
    # számlázó rendszerben készül, de a PDF-jét ide is fel lehet tölteni, hogy
    # a havi könyvelési csomagban (lásd routes/finance.py szamlak_zip) a
    # kimenő számlák is benne legyenek, ne csak a bejövők.
    szamla_filename: Mapped[str | None] = mapped_column(String(255), comment="A feltöltött kimenő számla fájlneve")
    szamla_storage_key: Mapped[str | None] = mapped_column(String(500))
    szamla_file_url: Mapped[str | None] = mapped_column(String(500))

    # a bevétel-táblák maradék mezői
    nev: Mapped[str | None] = mapped_column(String(255), comment="Name")
    forint_netto_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Forint nettó")
    plusz_afa: Mapped[str | None] = mapped_column(String(50), comment="+ÁFA")
    mikor_fizetett: Mapped[str | None] = mapped_column(String(120))
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    arfolyam: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # ── Devizás felvezetés ──────────────────────────────────────────────────
    # Ugyanaz a szabály, mint a kiadásnál (lásd services/penznem.py): a
    # `netto`/`brutto` mindig forint, itt marad meg, miből lett.
    eredeti_penznem: Mapped[str | None] = mapped_column(
        String(10), comment="Milyen pénznemben vezették fel (NULL = forintban)"
    )
    eredeti_netto: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="A nettó az eredeti pénznemben")
    eredeti_brutto: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="A bruttó az eredeti pénznemben")

    project_code: Mapped["ProjectCode"] = relationship(back_populates="revenues")
    payments: Mapped[list["Payment"]] = relationship(back_populates="revenue")


class KpForgalom(TimestampMixin, Base):
    """KP forgalom - önálló entitás, kapcsolódik az Expense-hez, de nem olvad bele."""

    __tablename__ = "kp_forgalmak"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    forgalom: Mapped[str | None] = mapped_column(String(50), comment="bevetel / kiadas")
    osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    legalis: Mapped[str | None] = mapped_column(String(50))
    kiadas_datuma: Mapped[date | None] = mapped_column(Date)

    kiadas_sum_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Kiadás sum")
    forintban_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Forintban")
    megnevezes: Mapped[str | None] = mapped_column(String(255))

    expense: Mapped["Expense"] = relationship(back_populates="kp_forgalmak")

    @property
    def forintban(self) -> float | None:
        """Az összeg forintra váltva - az árfolyam-logikát a FinanceService számolja."""
        return self.osszeg if self.penznem == "HUF" else None
