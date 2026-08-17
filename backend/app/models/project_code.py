from datetime import date
from typing import Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProjectCode(TimestampMixin, Base):
    """Pénzügyi egység - 1 Project Code : N Project (forgatás). A pénzügyi mag.

    A 'HYPE ADMIN projektkódok' Notion tábla 81 mezős - a felhasználó döntése alapján
    (2026-07-02) minden mező saját, névvel ellátott oszlopot kap (nem egy közös JSON
    "extra" mezőbe zsúfolva). Kivétel: a puszta Notion buttonök (sosem hordoznak
    adatot), és azok a relationök, amik már úgyis megvannak a mi valódi, fordított
    irányú FK-jainkkal (pl. 'Utómunka'/'Bevételek'/'Forgatások'/'Projekt kiadások'/
    'Belsős extra kiadások' relationök - ezek ugyanazt az adatot duplikálnák, amit a
    Deliverable/Revenue/Project/Expense.project_code_id már helyesen hordoz).

    Sok Notion mező (formula/rollup) egy régi, Notion-oldali számítás pillanatképe -
    ahol van megbízható saját számításunk (pl. összes költség, profit), azt az
    `osszes_koltseg`/`becsult_profit` @property adja élőben, a Notion pillanatkép a
    `*_notion` nevű oszlopokban van, tájékoztató jelleggel."""

    __tablename__ = "project_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    projektkod: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))

    datum: Mapped[date | None] = mapped_column(Date)
    esemeny_allapota: Mapped[str | None] = mapped_column(String(50))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    arfolyam: Mapped[float | None] = mapped_column(Numeric(12, 4))
    szerzodes_url: Mapped[str | None] = mapped_column(String(500))
    tig_statusza: Mapped[str | None] = mapped_column(String(50))
    szamla_statusza: Mapped[str | None] = mapped_column(String(50))

    megjegyzes: Mapped[str | None] = mapped_column(Text)

    #: Van-e szerződés emögött a projekt mögött.
    #:
    #: Ez a kapcsoló dönti el, hogy kérünk-e papírt: ha VAN szerződés, akkor a
    #: megrendelői eseti szerződés ÉS a teljesítési igazolás is jár hozzá
    #: (lásd models/megrendeloi_papir.py). Ha nincs, a projektkód
    #: papírozás-szempontból lezártnak számít.
    #:
    #: Alapértéke True: a szokásos eset az, hogy szerződünk - a kivételt kell
    #: külön jelölni, nem a szabályt.
    van_szerzodes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    #: Papír nélkül elszámolt projekt.
    #:
    #: Van olyan eset, amikor nem kell se szerződés, se TIG, mert a
    #: teljesítés nem klasszikus megrendelés: pl. a cégvezető be van jelentve
    #: a megrendelő céghez vállalkozóként, és a projekt ellenértéke úgy
    #: rendeződik, hogy ő ANNYIVAL KEVESEBB fizetést vesz fel onnan.
    #:
    #: Ilyenkor a bevétel NEM bejövő pénz, hanem el nem költött pénz - a
    #: pénzmozgás elmarad, a teljesítés viszont megtörtént. Ezért a projektkód
    #: nem "hiányos papírozású", hanem külön, megindokolt kategória: enélkül
    #: minden ilyen tétel örökre ott állna a teendők között.
    papir_nelkul: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    #: MIÉRT nincs papír. A jelöléshez kötelező (lásd routes/project_codes.py):
    #: fél év múlva ez az egyetlen dolog, amiből kiderül, mi történt.
    papir_nelkul_indoka: Mapped[str | None] = mapped_column(Text)
    teljesites_datuma: Mapped[date | None] = mapped_column(Date)
    utalas_datuma: Mapped[date | None] = mapped_column(Date)
    szamla_url: Mapped[str | None] = mapped_column(String(500))
    tig_alairva_url: Mapped[str | None] = mapped_column(String(500))

    # --- a maradék Notion mezők, egyenként ("Notion property" a kommentben) ---
    teljesites_datum_formazva: Mapped[str | None] = mapped_column(String(255), comment="Teljesítés dátum formáz")
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Nettó összeg")
    megrendelo_szekhelye: Mapped[str | None] = mapped_column(String(500), comment="Megrendelő  székhelye")
    profit_szazalek_notion: Mapped[dict | None] = mapped_column(JSON, comment="Profit százalék")
    geri_projekt: Mapped[str | None] = mapped_column(String(100), comment="Geri projekt")
    szerzodes_targya: Mapped[str | None] = mapped_column(String(255), comment="Szerződés tárgya")
    keltezes_datum_formazva: Mapped[str | None] = mapped_column(String(255), comment="Keltezés dátum formáz")
    gyartasi_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Gyártási költség")
    szerzodes_specialis_eset: Mapped[str | None] = mapped_column(Text, comment="Szerződés speciális eset")
    fizetesi_hatarido: Mapped[date | None] = mapped_column(Date, comment="Fizetési határidő")
    megrendelo_nyilvantartasi_szam: Mapped[str | None] = mapped_column(
        String(100), comment="Megrendelő nyilvántartásiszám"
    )
    szerzodes_kuldes: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), default=False, comment="Szerződés küldés"
    )
    osszes_koltseg_notion: Mapped[dict | None] = mapped_column(
        JSON, comment="Összes költség (Notion pillanatkép - élő érték: @property osszes_koltseg)"
    )
    tig_teljesitesi_ido: Mapped[str | None] = mapped_column(String(255), comment="TIG teljesítési idő")
    megrendelo_neve: Mapped[str | None] = mapped_column(String(255), comment="Megrendelő neve")
    osszesen_netto_notion: Mapped[dict | None] = mapped_column(JSON, comment="Összesen nettó")
    megrendelo_adoszama: Mapped[str | None] = mapped_column(String(50), comment="Megrendelő adószáma")
    netto_notion: Mapped[dict | None] = mapped_column(JSON, comment="Nettó")
    helyszin: Mapped[str | None] = mapped_column(String(255), comment="HELYSZÍN")
    datum_megjegyzes: Mapped[str | None] = mapped_column(Text, comment="DÁTUM megjegyzés")
    szerzodes_plusz_afa: Mapped[str | None] = mapped_column(String(100), comment="Szerződés plus ÁFA")
    tig_projektnev: Mapped[str | None] = mapped_column(String(255), comment="TIG projektnév")
    specialis_eset: Mapped[str | None] = mapped_column(Text, comment="Speciális eset")
    szerzodes_helye: Mapped[str | None] = mapped_column(String(100), comment="Szerződés helye")
    szerzodes_netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Szerződés nettó összeg")
    megrendeloi_emailek: Mapped[str | None] = mapped_column(Text, comment="megrendelői emailek")
    brutto_notion: Mapped[dict | None] = mapped_column(JSON, comment="Bruttó")
    kulsos_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Külsős (relation, nyers Notion page ID-k)")
    alvallalkozok_koltsege_notion: Mapped[dict | None] = mapped_column(JSON, comment="Alvállalkozók költsége")
    darabolva: Mapped[dict | None] = mapped_column(JSON, comment="Darabolva")
    vagasi_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Vágási költség")
    project_nev: Mapped[str | None] = mapped_column(String(255), comment="PROJECT NÉV")
    szerzodes_statusza: Mapped[str | None] = mapped_column(String(50), comment="Szerződés státusza")
    plusz_afa: Mapped[str | None] = mapped_column(String(100), comment="Plusz ÁFA")
    megerte_e: Mapped[dict | None] = mapped_column(JSON, comment="Megérte-e")
    megrendelo_kepviseloje: Mapped[str | None] = mapped_column(String(255), comment="Megrendelő képviselője")
    szerzodes_projekt_nev: Mapped[str | None] = mapped_column(String(255), comment="Szerződés projekt név")
    teljesites: Mapped[str | None] = mapped_column(Text, comment="Teljesítés")
    tig_kikuldve: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), default=False, comment="TIG kiküldve"
    )
    adminisztracios_tablaban: Mapped[str | None] = mapped_column(String(100), comment="ADMINISZTRÁCIÓS TÁBLÁBAN?")
    tig_specialis: Mapped[str | None] = mapped_column(Text, comment="TIG Speciális")
    keltezes_datuma: Mapped[date | None] = mapped_column(Date, comment="Keltezés dátuma")
    lejart_notion: Mapped[dict | None] = mapped_column(JSON, comment="Lejárt")
    megbizas_targya: Mapped[str | None] = mapped_column(String(255), comment="Megbízás tárgya")
    belsos_koltseg_akkor: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Belsős költség akkor")
    vallalasi_ar_notion: Mapped[dict | None] = mapped_column(JSON, comment="Vállalási ár")
    tovabbi_dokumentumok: Mapped[dict | None] = mapped_column(JSON, comment="További dokumentumok (files)")
    utomunkak_notion: Mapped[dict | None] = mapped_column(JSON, comment="Utómunkák (formula szöveg)")
    bevetel_formaja: Mapped[str | None] = mapped_column(String(100), comment="Bevétel formája")
    darabolas_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="HYPE ADMIN PROJEKTKÓDOK DARABOLÁS (relation, nyers Notion page ID-k)"
    )
    megrendelo_email: Mapped[str | None] = mapped_column(String(255), comment="Megrendelő email")
    forintban_notion: Mapped[dict | None] = mapped_column(JSON, comment="Forintban")
    szerzodes_keltezes_datuma: Mapped[date | None] = mapped_column(Date, comment="Szerződés keltezés dátuma")
    belsos_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Belsős költség")
    belso_plusz_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Belső plusz költség")
    tig_url: Mapped[str | None] = mapped_column(String(500), comment="TIG url")

    client: Mapped["Client"] = relationship(back_populates="project_codes")
    contract: Mapped["Contract"] = relationship(back_populates="project_codes")
    projects: Mapped[list["Project"]] = relationship(back_populates="project_code")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="project_code")
    revenues: Mapped[list["Revenue"]] = relationship(back_populates="project_code")
    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="project_code")
    #: A megrendelői papírok - CSAK OLVASÁSRA (viewonly): a papírok életét a
    #: saját végpontjuk intézi (lásd routes/megrendeloi_papirok.py), ide azért
    #: kellenek, hogy a lista egy lekérdezésből tudja, hol tart a papírozás.
    megrendeloi_szerzodesek: Mapped[list["MegrendeloiSzerzodes"]] = relationship(viewonly=True)
    megrendeloi_tigek: Mapped[list["MegrendeloiTig"]] = relationship(viewonly=True)

    # ── Hol tart a papírozás és a pénz? ──────────────────────────────────────
    #
    # Ezek a jelzők a listán mutatják meg, MELYIK projekten van már szerződés,
    # hol van kész TIG, és mi az, amit még nem fizettek ki. A szabály nem itt
    # dől el: a "kell-e papír" a services/megrendeloi_papir.papirt_igenyel-é,
    # a "kész-e egy papír" a LEZART_ALLAPOTOK-é - ugyanaz, amit a papír-oldalak
    # használnak, hogy a lista ne mondhasson mást, mint az adatlap.

    @property
    def papir_kell(self) -> bool:
        from app.services.megrendeloi_papir import papirt_igenyel

        return papirt_igenyel(self)

    @staticmethod
    def _van_kesz_papir(papirok: list) -> bool:
        from app.models.megrendeloi_papir import LEZART_ALLAPOTOK

        return any(p.allapot in LEZART_ALLAPOTOK for p in papirok)

    @property
    def keret_fedi(self) -> bool:
        """Fedi-e a munkát ÉLŐ megrendelői keretszerződés.

        Ha igen, eseti szerződés nem kell - a keret pont azért van, hogy ne
        kelljen munkánként újraszerződni. A TIG-et viszont nem váltja ki: az
        arról szól, hogy egy konkrét munka elkészült. Ugyanez a szabály az
        alvállalkozói oldalon is."""
        from app.services.megrendeloi_papir import megrendeloi_keret_ervenyes

        if self.client is None:
            return False
        return any(megrendeloi_keret_ervenyes(c, self.datum) for c in self.client.contracts)

    @property
    def szerzodes_kesz(self) -> bool:
        """Van-e a megrendelővel LEZÁRT eseti szerződés ezen a projektkódon.

        Egy projektkódhoz több papír is tartozhat (társfinanszírozás, elrontott
        és újrakezdett példány), ezért elég, ha az egyik lezárt."""
        return self._van_kesz_papir(self.megrendeloi_szerzodesek)

    @property
    def szerzodes_kell(self) -> bool:
        """Kell-e egyedi (eseti) szerződés: keret alatt nem."""
        return self.papir_kell and not self.keret_fedi

    @property
    def tig_kesz(self) -> bool:
        return self._van_kesz_papir(self.megrendeloi_tigek)

    @property
    def bevetel_kifizetve(self) -> bool:
        """Megérkezett-e a pénz: van bevétel-sor, és MINDEGYIK ki van fizetve.

        Bevétel-sor nélkül hamis: olyankor nem tudunk pénzről, tehát nem
        mondhatjuk, hogy megjött. A lista így hozza előre azt is, ahol csak
        elfelejtették felvezetni."""
        bevetelek = list(self.revenues)
        return bool(bevetelek) and all(r.fizetes_datuma is not None for r in bevetelek)

    @staticmethod
    def _osszeg(sor: Any) -> float:
        """Egy kiadás/bevétel összege: a BRUTTÓ, ha meg van adva, különben a
        nettó.

        A Pénzügyek felületén (és a projektkód adatlapján) a kézzel felvitt
        tételnél csak a NETTÓ mezőt kérjük be - a bruttó jellemzően csak a
        Notionból hozott soroknál van kitöltve. Amíg csak a bruttót néztük, a
        kézzel felvezetett kiadások NULLÁNAK számítottak: a projekt költsége
        úgy nézett ki, mintha nem is lettek volna.

        ÁFÁ-t nem tippelünk rá: a nettó legalább IGAZ, egy kitalált 27% nem
        feltétlenül (nem minden szállító áfás, és nem mindegyik 27%)."""
        if sor.brutto is not None:
            return float(sor.brutto)
        return float(sor.netto or 0)

    def _kulsos_bontas(self) -> tuple[float, float]:
        """(külsős, egyéb) - egy menetben, mert a kettő ugyanazon a szűrésen
        osztozik, és külön-külön kiszámolva kétszer járnánk be mindent."""
        from app.models.employee import EmployeeType
        from app.services import kulsos_koltseg

        # A külsős munka ára a TIG-eken áll (az ide tartozó forgatásokra eső
        # rész), nem a belőlük keletkezett Kiadás soron: így a még KI NEM
        # FIZETETT, de már beadott számla is látszik a projekt költségében.
        # A TIG-ből származó Kiadás sorokat ezért kihagyjuk - ugyanaz a pénz.
        tig_osszeg, tig_kiadas_idk = kulsos_koltseg.projektkod_kulsos(self)

        kulsos = tig_osszeg
        egyeb = 0.0
        for e in self.expenses:
            if e.id in tig_kiadas_idk:
                continue
            osszeg = self._osszeg(e)
            # A TIG-en kívüli külsős kifizetéseket két jelről ismerjük fel: a
            # sor `tipus="kulsos"` jelöléséről, vagy a hozzá kötött EMBER
            # típusáról - a Notionból hozott soroknál a "Kiadás formája"
            # szabad szöveg volt, arra nem lehet szabályt építeni.
            if (e.tipus or "").strip().lower() == "kulsos" or (
                e.employee is not None and e.employee.tipus == EmployeeType.KULSOS
            ):
                kulsos += osszeg
            else:
                egyeb += osszeg
        return kulsos, egyeb

    @property
    def kulsos_koltseg(self) -> float:
        """A KÜLSŐS közreműködők ára: az ide tartozó forgatásokra szóló TIG-ek
        (a rájuk eső rész, bruttóban) + a TIG-en kívüli külsős kifizetések.

        A be nem fizetett számla is ide tartozik: a pénz akkor is ki fog menni,
        és a projekt profitja addig sem hazudhat."""
        return self._kulsos_bontas()[0]

    @property
    def egyeb_kiadas(self) -> float:
        """Minden más Kiadás sor: bérlés, utazás, kellék, belsős extra…

        Nem felsorolás, hanem MARADÉK - így a négy költség-rész összege pontosan
        az `osszes_koltseg`, nem marad ki semmi egy hiányzó kategória miatt."""
        return self._kulsos_bontas()[1]

    @property
    def vagas_koltseg(self) -> float:
        """Az utómunka ára: a vágások mért idejéből számolt költség
        (Deliverable.koltseg, lásd services/deliverable_actions.py)."""
        return float(sum(d.koltseg or 0 for d in self.deliverables))

    @property
    def belsos_munka_koltseg(self) -> float:
        """A projektkód alatti forgatásokon dolgozó BELSŐSÖK napidíja.

        Nem kiadás-sor, csak számítás: a belsős alapbére a hónap végén EGYBEN
        kerül a kiadások közé, itt csak azt látjuk, mennyi saját munka van
        ebben a projektben (lásd services/belsos_koltseg.py)."""
        from app.services import belsos_koltseg

        return belsos_koltseg.projektkod_koltsege(self)

    @property
    def osszes_koltseg(self) -> float:
        """Számított: az összes projektkiadás (alvállalkozói/belsős TIG-ekből
        keletkezett Expense-ek is ide tartoznak, hiszen azok is Expense-ként
        jönnek létre - lásd performance_certificates.py /szamla-kifizetve) +
        az utómunka/vágási költség (Deliverable.koltseg) + a projekten dolgozó
        BELSŐSÖK napidíja. Ez a projekt VALÓS teljes költsége - szándékosan nem
        szűri a Pénzügy-gate (hozzaadas_a_kiadasokhoz), mert az csak a globális
        Pénzügy nézet összesítőit korlátozza (lásd api/routes/finance.py), nem
        azt, hogy mi számít az adott projekt költségének.

        A belsős napidíj azért van benne, mert nélküle a saját emberünk munkája
        ingyennek látszana, és minden projekt profitja szebb lenne a
        valóságnál. A Pénzügyek kiadás-listáját ez NEM érinti: oda a belsős bér
        a hónap végén, egy tételben kerül be."""
        # Négy rész, amit az adatlap külön-külön is kiír: külsős stáb, egyéb
        # kiadás, vágás, belsős munkanapok. Mindegyik float (a pénzoszlopok
        # Numeric-ek, a napidíj viszont számított float - a kettő közvetlen
        # összeadása TypeError-t dobna).
        kulsos, egyeb = self._kulsos_bontas()
        return kulsos + egyeb + self.vagas_koltseg + self.belsos_munka_koltseg

    @property
    def bevetel(self) -> float:
        """A projektkódhoz tartozó bevételek BRUTTÓ összege.

        Külön property, mert a listán is látszania kell: a profit önmagában
        nem mondja meg, nagy bevételből maradt-e kevés, vagy kicsiből sok.

        Ha a bruttó nincs kitöltve, a nettó számít - lásd `_osszeg`: a kézzel
        felvitt bevételnél is csak a nettót kérjük be."""
        return float(sum(self._osszeg(r) for r in self.revenues))

    @property
    def becsult_profit(self) -> float:
        return self.bevetel - self.osszes_koltseg
