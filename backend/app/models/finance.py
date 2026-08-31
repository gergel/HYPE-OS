from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Expense(TimestampMixin, Base):
    """Kiadás - Kiadások + Projekt kiadások + Belsős extra kiadások egyesítve."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A felületen "Cégnév" a címkéje (a felhasználó kérése): KINEK fizettünk.
    #: A Notionből importált sorokban is jellemzően a cég/partner neve áll itt.
    megnevezes: Mapped[str] = mapped_column(String(255), nullable=False)
    #: A felületen "Megnevezés": MIRE ment a kiadás (a felhasználó kérése) -
    #: a `megnevezes` a partner, ez a tétel leírása.
    kiadas_leiras: Mapped[str | None] = mapped_column(Text)
    #: Ha a nettóhoz "+ÁFA"-t jelöltek (lásd `plusz_afa`), hány százalékkal -
    #: ebből számolja a szerver a bruttót (lásd routes/finance._afa_brutto).
    afa_szazalek: Mapped[float | None] = mapped_column(Numeric(5, 2))

    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    #: ALVÁLLALKOZÓI kiadás: ha ki van töltve, ez a kiadás egy konkrét
    #: forgatáshoz (Project) köti az `employee_id` embert úgy, hogy tőle
    #: (mint alvállalkozótól) SZERZŐDÉS és TELJESÍTÉSI IGAZOLÁS is kell,
    #: ugyanúgy, mint egy külsős stábtagtól - de ANÉLKÜL, hogy a projekt
    #: stábjába (project.crew) kerülne, tehát a diszpó (stáblista, forgatási
    #: behívó) sosem hívja be. Lásd models/project.py Project.alvallalkozo_stab
    #: és api/routes/subcontractor_contracts.py szerzodest_igenylo_emberek.
    #:
    #: NEM kötelező kézzel megadni: a szerver a kiadás projektkódjának
    #: legfrissebb forgatásához automatikusan hozzárendeli (lásd
    #: api/routes/finance.py _alvallalkozo_forgatas_kitoltese) - elég az
    #: alvállalkozót magát kiválasztani, "csak a projektkódhoz" hozzáadva. Ha
    #: a projektkódhoz MÉG egy forgatás sem tartozik (tisztán ügynökségi
    #: feladat, nincs forgatás), a mező üresen marad - ilyenkor az Utókövetés
    #: közvetlenül a PROJEKTKÓDHOZ köti a szerződést/TIG-et (lásd
    #: models/project_code.py ProjectCode.alvallalkozo_stab_forgatas_nelkul).
    alvallalkozo_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
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
    #: Melyik projekthez tartozik ez a KP kiadás/bevétel - önálló hivatkozás,
    #: FÜGGETLEN az expense_id-tól: ez csak egy egyszerű címke ("innen
    #: átvezetve"), nem egy már máshol elszámolt tétel duplikátuma, tehát a
    #: kassza-összesítésből NEM esik ki miatta (ellentétben az expense_id-vel
    #: kötött sorokkal - lásd services/kassza.py "kotve" szűrése).
    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))

    forgalom: Mapped[str | None] = mapped_column(String(50), comment="bevetel / kiadas")
    osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    #: Devizás felvezetés: a `penznem`-ben megadott összeget a szerver váltja
    #: át forintra ezzel (lásd services/penznem.py) - az `osszeg` mezőbe már a
    #: forint kerül. Forintnál elhagyható.
    arfolyam: Mapped[float | None] = mapped_column(Numeric(10, 4))
    #: MIBŐL lett a forint összeg - devizás felvezetésnél (services/penznem.py).
    eredeti_penznem: Mapped[str | None] = mapped_column(
        String(10), comment="Milyen pénznemben vezették fel (NULL = forintban)"
    )
    eredeti_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Az összeg az eredeti pénznemben")
    legalis: Mapped[str | None] = mapped_column(String(50))
    kiadas_datuma: Mapped[date | None] = mapped_column(Date)
    #: Van-e mögötte SZÁMLA - a felhasználó KÉZZEL állítja (legördülő: van /
    #: nincs), nem a feltöltött fájlból derül ki: a bizonylat-feltöltés csak
    #: akkor jelenik meg a felületen, ha ez igazra van állítva (lásd frontend
    #: components/finance/KpForgalomSzamlaCella.tsx).
    van_szamla: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    kiadas_sum_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Kiadás sum")
    forintban_notion: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Forintban")
    megnevezes: Mapped[str | None] = mapped_column(String(255))
    #: A Notion-oldal ÖSSZES property-je nyersen, ahogy az import látta
    #: ({mezőnév: érték}) - a felhasználó kérése, hogy a KP forgalom EGY AZ
    #: EGYBEN jöjjön át: a tipizált oszlopokba a felismerhető mezők kerülnek,
    #: ez a tükör pedig garantálja, hogy olyan Notion-mező sem veszik el,
    #: amiről az import nem tud (lásd importers_wave2.import_kp_forgalom).
    notion_adatok: Mapped[dict | None] = mapped_column(JSON, comment="A Notion-oldal összes property-je nyersen")

    expense: Mapped["Expense"] = relationship(back_populates="kp_forgalmak")
    project_code: Mapped["ProjectCode | None"] = relationship()

    @property
    def forintban(self) -> float | None:
        """A sor ELŐJELES forint értéke: NEGATÍV = kiadás, pozitív = bevétel.

        Az előjel a Notion **"Forintban"** formulájából jön - abban a táblában
        ez hordozza az irányt, nem a "Forgalom" szöveges mező. Az "Összeg"
        oszlop előjel nélküli, tehát önmagában nem lehet megmondani belőle, egy
        600 000 Ft-os sor kivétel volt-e a kasszából vagy betétel.

        (A Notionnel való egyeztetéskor ez 132 sornál ütött ki: mindegyiknél
        stimmelt a szám, csak nálunk bevételként állt, ami valójában kiadás -
        lásd scripts/kp_forgalom_egyeztetes.py.)

        Ahol a formula-mező nem jött át, marad az "Összeg" - az előjel nélkül;
        olyankor a `forgalom` szöveges mező dönt (lásd services/kassza.py).

        A pénznemet a közös szabály szerint ismerjük fel (lásd
        services/penznem.py), nem `== "HUF"` egyenlőséggel: a Notionben ez
        szabad szöveg volt, magyarul kitöltve, tehát a sorok nagy részén
        "Forint" áll. A szigorú egyenlőség ezeket mind DEVIZÁSNAK látta, és
        None-t adott rájuk - vagyis a kassza összesítéséből annyi forint
        hiányzott, ahány ilyen sor van."""
        from app.services import penznem as penznem_szolg

        if self.forintban_notion is not None:
            return float(self.forintban_notion)
        if penznem_szolg.devizas(self.penznem):
            # Valódi devizás sor forint-érték nélkül: egy devizás összeget
            # forintként kezelni nagyságrendi hiba lenne.
            return None
        return float(self.osszeg) if self.osszeg is not None else None

    @property
    def kiadas_e(self) -> bool:
        """Kivétel-e a kasszából. Ugyanaz a szabály, amit a kassza használ -
        hogy a felület ne vezethesse le máshogy (lásd services/kassza.py)."""
        from app.services.kassza import kp_forgalom_iranya

        return kp_forgalom_iranya(self)[1]

    @property
    def atvezetes_e(self) -> bool:
        """ATM-felvétel-e: a bankszámláról a kasszába tett SAJÁT pénz. A kassza
        egyenlegét mozgatja, de se a legális, se a fekete oldalra nem kerül
        (lásd services/kassza.py)."""
        from app.services.kassza import keszpenzfelvetel

        return keszpenzfelvetel(self.megnevezes)
