from datetime import date
from typing import Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
# Az elszámolás közös szabálya (nettó a mérvadó). Behúzható modul szinten is:
# csak az SQLAlchemy-től függ, tehát nem csinál körbe-importot a modellekkel -
# a kulsos_koltseg / belsos_koltseg viszont igen, azok ezért maradnak lentebb,
# a metódusokon belüli importban.
from app.services import elszamolas


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

    #: A megrendelő. SZÁNDÉKOSAN opcionális: egy projektkód gyakran korábban
    #: születik meg (a következő szabad sorszámot lefoglaljuk), mint ahogy
    #: eldőlne, kinek dolgozunk rajta - a felvételkor ezért nem kérjük.
    #: Ami rá épül, kezeli a hiányát (lásd services/megrendeloi_papir.py:
    #: ügyfél nélkül nincs keretszerződés-fedés, tehát eseti szerződés kell).
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
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

    #: "Kifizetve, de NE kerüljön a bevételek közé."
    #:
    #: A számla-lépés lezárásakor alapból bevétel-sor keletkezik (az a pénz
    #: tényleg megjött). Van viszont olyan eset, amikor a munka ki van
    #: fizetve, de a Pénzügyekbe nem való: beszámították valamibe, egy másik
    #: cégen át folyt be, vagy már máshol el van könyvelve. Ilyenkor a
    #: projektkód mégis LEZÁRT (nem áll örökre a teendők között), csak nincs
    #: mögötte bevétel-sor - és ide van írva, miért.
    bevetelbe_ne_keruljon: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    #: MIÉRT nem kerül a bevételek közé - a jelöléshez kötelező.
    bevetel_kihagyas_oka: Mapped[str | None] = mapped_column(Text)

    #: "Erről a munkáról nincs számla."
    #:
    #: Van, amit nem a megszokott módon fizetnek: nincs kiállított számla,
    #: tehát fizetési határidő sincs - a pénz viszont megjött (vagy másképp
    #: rendeződött). A számla-lépés ilyenkor is lezárható, csak a határidőt
    #: nem kérjük számon (lásd services/megrendeloi_szamla.py).
    szamla_kihagyva: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    #: MIÉRT nincs számla - a jelöléshez kötelező.
    szamla_kihagyas_oka: Mapped[str | None] = mapped_column(Text)

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
        """Fedi-e EZT a munkát megrendelői keretszerződés.

        A kérdés a PROJEKTKÓDRA vonatkozik, nem az ügyfélre: az számít, hogy
        ehhez a kódhoz oda van-e kötve egy élő keretszerződés (`contract_id`).

        Korábban azt néztük, van-e az ÜGYFÉLNEK bármilyen élő kerete - ez
        tömegesen hazudott: egyetlen keretszerződéstől a megrendelő ÖSSZES
        munkája "keretszerződés alatt"-nak látszott, azok is, amikre a keret
        nem terjed ki, és amikre a Notion sem így hivatkozik. Márpedig ez a
        jelölés teendőt tüntet el (eseti szerződést nem kérünk) - tévesen
        állítva pont a hiányzó papírokat rejti el.

        A kötést a Notion-import hozza (a projektkód "Keretszerződés"
        relationjéből, lásd notion_import/importers.py), illetve a szerződés
        készítésekor lehet ráállítani (routes/megrendeloi_papirok.py).

        A TIG-et ez NEM váltja ki: a keret arról szól, milyen feltételekkel
        dolgozunk együtt, a TIG arról, hogy egy konkrét munka elkészült."""
        from app.services.megrendeloi_papir import megrendeloi_keret_ervenyes

        if self.contract is None:
            return False
        return megrendeloi_keret_ervenyes(self.contract, self.datum)

    @property
    def keretszerzodes_neve(self) -> str | None:
        """KIVEL van a keretszerződés - a felület ezt írja ki a "keretszerződés
        alatt" jelzés mellé. Egy puszta "keretszerződés alatt" ugyanis nem
        ellenőrizhető: pont az a kérdés, melyik céggel."""
        if self.contract is None or not self.keret_fedi:
            return None
        return self.contract.ceg_neve or (self.contract.client.nev if self.contract.client else None)

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
        elfelejtették felvezetni.

        KIVÉTEL: ha valaki kimondta, hogy a pénz megjött, de ez a tétel nem
        való a bevételek közé (beszámították, máshol könyvelték - lásd
        bevetelbe_ne_keruljon), akkor a kifizetés dátuma önmagában lezárja. Ez
        nem "szemet hunyás": a jelöléshez indok is kell, és az ott marad a
        projektkódon."""
        if self.bevetelbe_ne_keruljon and self.utalas_datuma is not None:
            return True
        bevetelek = list(self.revenues)
        return bool(bevetelek) and all(r.fizetes_datuma is not None for r in bevetelek)

    @staticmethod
    def _osszeg(sor: Any) -> float:
        """Egy kiadás/bevétel elszámolási összege: a NETTÓ (lásd
        services/elszamolas.py).

        Bevételnél és kiadásnál ugyanaz a szabály - enélkül a kettő
        különbsége, vagyis a projekt profitja, a két oldal ÁFA-tartalmának
        különbségével csúszna el. Ha egy régi soron csak bruttó van, arra
        esünk vissza: adathiányban az a legjobb közelítés (ÁFÁ-t viszont nem
        számolunk vissza belőle - a 27%-os osztás ugyanolyan találgatás lenne,
        mint a felszorzás)."""
        return elszamolas.osszeg(sor)

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
        (a rájuk eső rész, nettóban) + a TIG-en kívüli külsős kifizetések.

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
    def _anyagok(self) -> list[Any]:
        """A projektkódhoz tartozó összes vágandó anyag: a rá közvetlenül
        kötöttek ÉS a forgatásain lógók, ismétlés nélkül."""
        anyagok = {d.id: d for d in self.deliverables}
        for projekt in self.projects:
            for d in getattr(projekt, "deliverables", []) or []:
                anyagok.setdefault(d.id, d)
        return list(anyagok.values())

    @property
    def vagas_koltseg(self) -> float:
        """Az utómunka ára: a MÉRT munkaidőből (Timesheet) számolt költség -
        ugyanaz a szám, ami az anyag oldalán a "Munkaidő-elszámolások" tábla
        alján áll (lásd services/deliverable_actions.anyag_osszesitok).

        SZÁNDÉKOSAN nem a `Deliverable.koltseg` mező: az egy régi, kézzel vagy
        importból beírt összeg, ami nem követi a méréseket. Egy utólag
        rögzített (vagy törölt) munkaidő-sor után ott elavult szám marad, és a
        projekt költsége azzal hazudna.

        Ha egy anyagon EGYÁLTALÁN nincs mérés (régi, Notionból hozott sorok),
        marad a rögzített mező: nullát írni oda rosszabb hazugság lenne, mint
        egy régi szám (lásd deliverable_actions.anyag_koltsege). Munkamenet
        nélküli (leválasztott) példánynál ugyanez."""
        from sqlalchemy import inspect as sa_inspect
        from sqlalchemy.orm import object_session

        from app.services import deliverable_actions

        anyagok = self._anyagok
        db = object_session(self)
        if db is None:
            return float(sum(d.koltseg or 0 for d in anyagok))

        # Ha a mérések MÁR BE VANNAK TÖLTVE (a lista-lekérdezés eager loaddal
        # hozza őket), a kapcsolatból dolgozunk - enélkül a lista soronként
        # indítana egy-egy lekérdezést, ami több száz körré hízna.
        betoltott = all("timesheets" not in sa_inspect(d).unloaded for d in anyagok)
        if betoltott:
            sorok = [t for d in anyagok for t in (d.timesheets or [])]
            osszesitok = deliverable_actions.sorok_osszesitese(db, sorok)
        else:
            osszesitok = deliverable_actions.anyag_osszesitok(db, [d.id for d in anyagok])
        return float(sum(deliverable_actions.anyag_koltsege(osszesitok, d) for d in anyagok))

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
        """A projektkódhoz tartozó bevételek NETTÓ összege.

        Külön property, mert a listán is látszania kell: a profit önmagában
        nem mondja meg, nagy bevételből maradt-e kevés, vagy kicsiből sok.

        Nettó, mert a költség oldalán is az van (lásd `_osszeg` és
        services/elszamolas.py) - két különböző szemlélet különbsége nem
        profit, hanem ÁFA.

        KIVÉTEL: ha a munka ki van fizetve, de szándékosan NEM került a
        bevételek közé (beszámítás, másik cégen át rendezve - lásd
        bevetelbe_ne_keruljon), akkor a papírokon/projektkódon szereplő összeg
        számít. A pénz ugyanis megjött; csak a Pénzügyek nyilvántartásába nem
        való, mert ott duplázna. Enélkül ezeknél a munkáknál nulla bevétel és
        csupa veszteség látszana - vagyis pont a profit hazudna arról, amiért
        ez a szám van."""
        sorok = float(sum(self._osszeg(r) for r in self.revenues))
        if sorok or not self.bevetelbe_ne_keruljon:
            return sorok
        from app.services import projektkod_osszeg

        netto, _ = projektkod_osszeg.szamlazott_osszeg(self)
        return float(netto or 0)

    @property
    def becsult_profit(self) -> float:
        return self.bevetel - self.osszes_koltseg
