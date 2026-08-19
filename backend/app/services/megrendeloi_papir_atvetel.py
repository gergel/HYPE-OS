"""A Notionból örökölt megrendelői papírok átvétele valódi rekordokba.

A HYPE ADMIN projektkódok Notion-táblában minden projekthez ott van, hogy
készült-e megrendelői szerződés és teljesítési igazolás, milyen névre, milyen
dátummal és összeggel - és oda vannak feltöltve maguk a papírok is. Ezt az
import már áthozta, de LAPOS MEZŐKBE (`szerzodes_statusza`, `tig_statusza`,
`megrendelo_neve`, ...) és általános csatolmányokba: szöveg, amiből a rendszer
nem tud papírt csinálni.

Ez a modul azt a szöveget alakítja `MegrendeloiSzerzodes` / `MegrendeloiTig`
rekorddá - ugyanazzá, amit a felület készít -, hogy a régi papírok is
megjelenjenek a gyűjtőoldalakon, és ne "hiányzó papírként" álljanak örökre a
teendők között.

KÉT HELYRŐL HÍVJUK, ugyanazzal a viselkedéssel:

- a Notion-import után (lásd notion_import/importers_megrendeloi.py), hogy egy
  újraimportálás is naprakészen tartsa;
- egy adatmigrációból, hogy a MÁR importált adatból azonnal meglegyen, Notion-
  hozzáférés nélkül is.

IDEMPOTENS: projektkódonként legfeljebb egy átvett szerződést és egy átvett
TIG-et tart nyilván, és újrafuttatáskor azt frissíti. Amit a felületen kézzel
készítettek, ahhoz NEM nyúl - ott már élő folyamat van, azt egy import nem
írhatja felül.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Number

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import Contract, ContractType
from app.models.document_attachment import DocumentAttachment
from app.models.finance import Revenue
from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig
from app.models.project_code import ProjectCode

#: Az átvett papírok állapota. Nem "Kiküldve", mert nem mi küldtük ki innen: a
#: papír MEGVAN, csak máshol készült. A felület pontosan ezt a különbséget
#: jelöli ezzel az értékkel, és lezártnak számít (LEZART_ALLAPOTOK).
ATVETT_ALLAPOT = "Van már papír"

#: A megjegyzés, amiből fél év múlva is látszik, honnan való a sor. Enélkül egy
#: hiányos adatú papírnál az lenne a kérdés, ki és mikor rontotta el - így
#: viszont látszik, hogy importált örökség.
ATVETT_MEGJEGYZES = "Notionból átvéve (HYPE ADMIN projektkódok)."

#: Állapot-szövegek, amik szerint NINCS papír. Ezeket előbb nézzük, mint a
#: "kész" jelzőket: a "Készíthető a TIG" és a "Nincs elkezdve" is tartalmaz
#: olyan szótövet ("kész", "elkezdve"), ami puszta részstring-kereséssel
#: tévesen késznek látszana.
NINCS_JELZOK: tuple[str, ...] = (
    # "Keretszerződése van": nincs is eseti papír, a keret váltja ki. Enélkül
    # is jó eredményt adna (nincs hozzá fájl), de jobb kimondani, mint a
    # hiányzó fájlra hagyatkozni.
    "keretszerződés",
    "keretszerzodes",
    "nincs elkezdve",
    "nincs még",
    "nincs",
    "készíthető",
    "keszitheto",
    "nem kell",
    "nem szükséges",
    "nem szukseges",
    "folyamatban",
    "hiányzik",
    "hianyzik",
    "elkezdve",
)

#: Állapot-szövegek, amik szerint MEGVAN a papír.
KESZ_JELZOK: tuple[str, ...] = (
    "elkészült",
    "elkeszult",
    "kiküldve",
    "kikuldve",
    "feltöltve",
    "feltoltve",
    "aláírva",
    "alairva",
    "megvan",
    "kész",
    "kesz",
)


def _ekezet_nelkul(szoveg: str) -> str:
    return szoveg.strip().casefold()


def allapot_kesz(statusz: str | None) -> bool | None:
    """A Notion állapot-szövege szerint megvan-e a papír?

    True / False / None - a None azt jelenti, hogy a szöveg nem dönti el
    (üres, vagy ismeretlen megfogalmazás). Ilyenkor a hívó a FÁJLOK alapján
    dönt, ami úgyis erősebb bizonyíték.

    A tagadó jelzőket vizsgáljuk előbb, lásd NINCS_JELZOK."""
    if not statusz or not statusz.strip():
        return None
    szoveg = _ekezet_nelkul(statusz)
    if any(jelzo in szoveg for jelzo in NINCS_JELZOK):
        return False
    if any(jelzo in szoveg for jelzo in KESZ_JELZOK):
        return True
    return None


def _elso_email(pk: ProjectCode) -> str | None:
    """A projektkódra örökölt megrendelői cím - szabad szöveg, több címmel."""
    nyers = (pk.megrendelo_email or pk.megrendeloi_emailek or "").strip()
    if not nyers:
        return None
    for elvalaszto in (",", ";", "\n"):
        nyers = nyers.replace(elvalaszto, " ")
    reszek = [r.strip() for r in nyers.split() if "@" in r]
    return reszek[0] if reszek else None


def _plusz_afa(ertek) -> bool | None:
    """A Notionban szöveges select ("+ ÁFA"), nálunk igen/nem."""
    if ertek in (None, "", []):
        return None
    if isinstance(ertek, bool):
        return ertek
    return "afa" in _ekezet_nelkul(str(ertek)).replace("á", "a")


def _szam(ertek) -> float | None:
    """Szám kinyerése a Notionból örökölt értékből.

    A HYPE ADMIN táblában az összegek fele FORMULA vagy ROLLUP: ezek nem sima
    számként jönnek át, hanem beágyazott szerkezetként ({"number": 500000},
    {"formula": {"number": …}}, listában a rollup elemei). Ha csak a
    `float(ertek)`-re hagyatkozunk, ezek mind None-ok lesznek - és pont az
    összeg hiányzik a papírról, amit a legkevésbé lehet kitalálni."""
    if ertek is None:
        return None
    if isinstance(ertek, bool):
        return None
    # Az adatbázisból Decimal jön (Numeric oszlop), a Notionból int/float -
    # mindkettő közvetlenül számmá alakítható.
    if isinstance(ertek, Number):
        return float(ertek)
    if isinstance(ertek, str):
        # "1 200 000 Ft" / "1.200.000" - a szóköz és a nem-szám karakterek
        # zajok, a tizedes vessző viszont számít.
        tisztitott = "".join(jel for jel in ertek if jel.isdigit() or jel in ",.-").replace(",", ".")
        # Ha ezer-elválasztó pontok is vannak, az utolsó pont a tizedesé.
        if tisztitott.count(".") > 1:
            elso, _, utolso = tisztitott.rpartition(".")
            tisztitott = elso.replace(".", "") + "." + utolso
        try:
            return float(tisztitott)
        except ValueError:
            return None
    if isinstance(ertek, dict):
        for kulcs in ("number", "formula", "rollup", "value", "array"):
            talalat = _szam(ertek.get(kulcs))
            if talalat is not None:
                return talalat
        return None
    if isinstance(ertek, (list, tuple)):
        for elem in ertek:
            talalat = _szam(elem)
            if talalat is not None:
                return talalat
    return None


def _url(ertek) -> str | None:
    """URL kinyerése bármilyen Notion-alakból (string, lista, objektum).

    Ugyanaz a mező lehet `url`, `files` vagy rich_text a Notionban, és a
    régebbi importok a nyers alakot írták az oszlopba. Egy lista alakú érték
    így "megvolt", de megnyithatatlan maradt - pont ez tüntette el a TIG
    PDF-jét a papírról."""
    if ertek is None:
        return None
    if isinstance(ertek, str):
        szoveg = ertek.strip()
        return szoveg if szoveg.startswith("http") else None
    if isinstance(ertek, dict):
        for kulcs in ("url", "external", "file"):
            talalat = _url(ertek.get(kulcs))
            if talalat:
                return talalat
        return None
    if isinstance(ertek, (list, tuple)):
        for elem in ertek:
            talalat = _url(elem)
            if talalat:
                return talalat
    return None


def _elso_kitoltott(*ertekek) -> str | None:
    """Az első nem üres szöveg - a papírok mezőinek tartalékláncához."""
    for ertek in ertekek:
        if ertek is None:
            continue
        szoveg = str(ertek).strip()
        if szoveg:
            return szoveg
    return None


#: Amit a papír mezői nem tudnak elnyelni, de kár lenne elveszíteni: a
#: Notionban ezek a "hogyan is volt ez pontosan" jegyzetek.
KIEGESZITO_MEZOK: tuple[tuple[str, str], ...] = (
    ("szerzodes_specialis_eset", "Szerződés speciális eset"),
    ("specialis_eset", "Speciális eset"),
    ("tig_specialis", "TIG speciális"),
    ("szerzodes_helye", "Szerződés helye"),
    ("adminisztracios_tablaban", "Adminisztrációs táblában"),
)


def _kiegeszito_megjegyzes(pk: ProjectCode) -> str:
    """Az átvétel-jelölés + a Notionból örökölt magyarázó szövegek.

    A papíron nincs külön oszlopuk, de a megjegyzésbe beírva ott maradnak
    annál a papírnál, amelyikről szólnak - és nem kell a projektkód nyers
    mezői közt keresgélni."""
    reszek = [ATVETT_MEGJEGYZES]
    for mezo, cimke in KIEGESZITO_MEZOK:
        ertek = _elso_kitoltott(getattr(pk, mezo, None))
        if ertek:
            reszek.append(f"{cimke}: {ertek}")
    return "\n".join(reszek)


@dataclass
class Atvetel:
    """Egy futás mérlege - a migráció és az import naplója ebből dolgozik."""

    szerzodes_letrejott: int = 0
    szerzodes_frissult: int = 0
    tig_letrejott: int = 0
    tig_frissult: int = 0
    kihagyott_projektkod: int = 0
    keret_ugyfelhez_kotve: int = 0
    #: A SZÁMLA-rész átvétele: hány bevétel-sor keletkezett/egészült ki, és
    #: hányhoz került oda a Notionba feltöltött számla.
    bevetel_letrejott: int = 0
    bevetel_frissult: int = 0
    szamla_fajl_atvéve: int = 0

    @property
    def osszes(self) -> int:
        return self.szerzodes_letrejott + self.tig_letrejott + self.bevetel_letrejott

    def __str__(self) -> str:
        return (
            f"szerződés: {self.szerzodes_letrejott} új / {self.szerzodes_frissult} frissítve, "
            f"TIG: {self.tig_letrejott} új / {self.tig_frissult} frissítve, "
            f"bevétel: {self.bevetel_letrejott} új / {self.bevetel_frissult} kiegészítve "
            f"({self.szamla_fajl_atvéve} számla fájllal), "
            f"papír nélküli projektkód: {self.kihagyott_projektkod}, "
            f"ügyfélhez kötött keretszerződés: {self.keret_ugyfelhez_kotve}"
        )


def kosd_ugyfelhez_a_kereteket(db: Session) -> int:
    """A megrendelői keretszerződések hozzákötése az ügyfelükhöz - a
    projektkódjaik felől.

    A Notion-import a keret ügyfelét az "Akivel szerződünk" relációból oldja
    fel (lásd notion_import/importers.import_contracts). Ahol ez a Notionban
    üresen maradt, a keret ügyfél NÉLKÜL jön át - és így használhatatlan: a
    "fedi-e a keret ezt a projektet" kérdés az ügyfélen dől el (lásd
    services/megrendeloi_papir.keretszerzodes_fedi), tehát az ilyen keret
    sosem váltaná ki az eseti szerződést.

    A hiányzó kapcsolat viszont kikövetkeztethető: ha projektkódok hivatkoznak
    a keretre, akkor annak az ügyfele a keret ügyfele. Csak akkor kötjük be,
    ha az összes hivatkozó projektkód UGYANAHHOZ az ügyfélhez tartozik -
    többféle ügyfélnél nem találgatunk, mert egy rossz kapcsolat rosszabb,
    mint a hiányzó (némán elhagyná az eseti szerződést egy olyan cégnél,
    amelyikkel valójában nincs keretünk).

    A meglévő kapcsolatot nem írja felül."""
    darab = 0
    keretek = db.scalars(
        select(Contract).where(Contract.tipus == ContractType.KERETSZERZODES, Contract.client_id.is_(None))
    ).all()
    for keret in keretek:
        ugyfel_idk = {
            sor
            for sor in db.scalars(
                select(ProjectCode.client_id).where(
                    ProjectCode.contract_id == keret.id, ProjectCode.client_id.is_not(None)
                )
            )
        }
        if len(ugyfel_idk) == 1:
            keret.client_id = ugyfel_idk.pop()
            darab += 1
    return darab


def _csatolmanyok(db: Session, project_code_id: int, kategoria: str) -> list[DocumentAttachment]:
    """A projektkódhoz importált fájlok egy kategóriában.

    A Notion-import a fájl szerepét a MEZŐ NEVÉBŐL állapítja meg (lásd
    notion_import/files.kategoria_mezonevbol), tehát a "TIG aláírva" mezőből
    jött fájl már "tig" kategóriában van, a szerződésé "szerzodes"-ben."""
    return list(
        db.scalars(
            select(DocumentAttachment)
            .where(
                DocumentAttachment.entity_type == "projectCode",
                DocumentAttachment.entity_id == project_code_id,
                DocumentAttachment.kategoria == kategoria,
            )
            .order_by(DocumentAttachment.id)
        )
    )


def _cegadat(pk: ProjectCode) -> dict:
    """A papírra került cégadat.

    A Notionból örökölt mezők az ELSŐDLEGESEK, nem az ügyfél mai adatlapja -
    fordítva, mint az ÚJ papírok előtöltésénél (lásd
    services/megrendeloi_papir.szerzodo_fel_adatai). Egy már megírt papír
    ugyanis azt kell hogy őrizze, ami RAJTA van: ha a cég azóta székhelyet
    váltott, a mai adat visszamenőleg átírná a történelmet. Az ügyfél adatlapja
    csak a lyukakat tölti ki."""
    ugyfel = pk.client
    return {
        "ceg_neve": pk.megrendelo_neve or (ugyfel.nev if ugyfel else None),
        "szekhely": pk.megrendelo_szekhelye or (ugyfel.szekhely if ugyfel else None),
        "adoszam": pk.megrendelo_adoszama or (ugyfel.adoszam if ugyfel else None),
        "kepviselo": pk.megrendelo_kepviseloje or (ugyfel.kepviselo if ugyfel else None),
        "nyilvantartasi_szam": (
            pk.megrendelo_nyilvantartasi_szam or (ugyfel.nyilvantartasi_szam if ugyfel else None)
        ),
        "email": _elso_email(pk),
        "client_id": pk.client_id,
        # A projektkódhoz kötött keretszerződés a papíron is látszik.
        "keretszerzodes_id": pk.contract_id,
    }


def szerzodes_mezoi(pk: ProjectCode) -> dict:
    """Az eseti szerződés adatai a projektkód Notion-örökségéből.

    A szerződés-specifikus mező az elsődleges (a Notionban külön oszlop van a
    szerződés tárgyára, összegére, keltezésére), és az általános mező a
    tartalék - a régi sorokon jellemzően csak az egyik van kitöltve."""
    return {
        **_cegadat(pk),
        "megbizas_targya": _elso_kitoltott(pk.szerzodes_targya, pk.megbizas_targya, pk.project_nev),
        "projekt_nev": _elso_kitoltott(pk.szerzodes_projekt_nev, pk.project_nev, pk.tig_projektnev),
        "teljesites_szoveg": _teljesites_szoveg(pk, pk.teljesites, pk.tig_teljesitesi_ido),
        "netto_osszeg": _netto(pk, pk.szerzodes_netto_osszeg, pk.netto_osszeg),
        "plusz_afa": _plusz_afa(pk.szerzodes_plusz_afa) or _plusz_afa(pk.plusz_afa),
        "keltezes": pk.szerzodes_keltezes_datuma or pk.keltezes_datuma or pk.teljesites_datuma,
    }


def tig_mezoi(pk: ProjectCode) -> dict:
    """A teljesítési igazolás adatai - a TIG-specifikus mezőkkel elöl."""
    return {
        **_cegadat(pk),
        "megbizas_targya": _elso_kitoltott(pk.megbizas_targya, pk.szerzodes_targya, pk.project_nev),
        "projekt_nev": _elso_kitoltott(pk.tig_projektnev, pk.project_nev, pk.szerzodes_projekt_nev),
        "teljesites_szoveg": _teljesites_szoveg(pk, pk.tig_teljesitesi_ido, pk.teljesites),
        "netto_osszeg": _netto(pk, pk.netto_osszeg, pk.szerzodes_netto_osszeg),
        "plusz_afa": _plusz_afa(pk.plusz_afa) or _plusz_afa(pk.szerzodes_plusz_afa),
        "keltezes": pk.keltezes_datuma or pk.teljesites_datuma or pk.szerzodes_keltezes_datuma,
    }


def _teljesites_szoveg(pk: ProjectCode, *elsok) -> str | None:
    """MIKOR teljesítettünk - szabad szöveg a papírra.

    A Notionban ez háromféleképp van meg: külön szöveges mezőként, formázott
    dátumként, vagy csak a valódi teljesítés-dátumként. A papíron egy sor van
    rá, tehát az elsőt vesszük, ami ki van töltve - és ha semmi, legalább a
    dátumot írjuk oda."""
    return _elso_kitoltott(
        *elsok,
        pk.teljesites_datum_formazva,
        pk.teljesites_datuma.strftime("%Y. %m. %d.") if pk.teljesites_datuma else None,
        pk.datum_megjegyzes,
    )


def _netto(pk: ProjectCode, *elsok) -> float | None:
    """A papírra kerülő nettó összeg.

    A projektkód-specifikus mezők után a Notion FORMULA/ROLLUP mezői jönnek
    (Nettó, Összesen nettó, Vállalási ár, Forintban): a régi soroknál sokszor
    csak ezekben van meg a szám. Egy összeg nélküli papír használhatatlan -
    inkább egy számított értékből induljunk ki, mint semmiből."""
    for ertek in (*elsok, pk.netto_notion, pk.osszesen_netto_notion, pk.vallalasi_ar_notion, pk.forintban_notion):
        szam = _szam(ertek)
        if szam:
            return szam
    return None


def _kell_e(statusz: str | None, van_fajl: bool, egyeb_jel: bool) -> bool:
    """Készült-e ez a papír a Notion szerint?

    A FÁJL a legerősebb bizonyíték: ha fel van töltve a papír, akkor megvan,
    bármit is mond az állapot-szöveg (a régi sorokon az állapot sokszor
    elmaradt a valóságtól). Utána jön az állapot-szöveg, végül az olyan egyéb
    jelzők, mint a "TIG kiküldve" jelölő."""
    if van_fajl:
        return True
    szoveg_szerint = allapot_kesz(statusz)
    if szoveg_szerint is not None:
        return szoveg_szerint
    return egyeb_jel


def _atvett_papir(db: Session, modell, project_code_id: int):
    """A KORÁBBAN ÁTVETT sor, ha van - ezt frissítjük újrafuttatáskor.

    Az átvett sorokat a megjegyzésük KEZDETE különbözteti meg a kézzel
    készítettektől: így egy újrafuttatás nem nyúl ahhoz, amit a felületen
    csináltak, és nem is készít mellé másodpéldányt. Azért a kezdete és nem a
    teljes egyezés, mert a megjegyzésbe a Notionból örökölt magyarázó szövegek
    is bekerülnek (lásd _kiegeszito_megjegyzes) - egy pontos egyezés ezeket
    "kézzel készített" papírnak nézné, és minden futáskor új másodpéldányt
    nyitna."""
    return db.scalars(
        select(modell)
        .where(
            modell.project_code_id == project_code_id,
            modell.megjegyzes.like(f"{ATVETT_MEGJEGYZES}%"),
        )
        .order_by(modell.id)
    ).first()


def _van_sajat_papir(db: Session, modell, project_code_id: int) -> bool:
    """Készült-e ezen a projektkódon KÉZZEL papír (nem importált)?

    Ha igen, az import nem szól bele: ott már élő folyamat van, és egy
    importált másodpéldány csak zavarna."""
    return (
        db.scalars(
            select(modell).where(
                modell.project_code_id == project_code_id,
                modell.megjegyzes.is_(None) | modell.megjegyzes.not_like(f"{ATVETT_MEGJEGYZES}%"),
            )
        ).first()
        is not None
    )


def _alkalmaz(papir, mezok: dict, fajl_url: str | None, megjegyzes: str = ATVETT_MEGJEGYZES) -> None:
    for mezo, ertek in mezok.items():
        if ertek is not None:
            setattr(papir, mezo, ertek)
    papir.megjegyzes = megjegyzes
    if fajl_url:
        # Az ALÁÍRT példány mezőjébe megy: a Notionba feltöltött papír a kész,
        # aláírt dokumentum, nem egy általunk generált piszkozat. Így a
        # felületen is "Kiküldve, aláírva"-ként, nem félkészként látszik.
        papir.allapot = ATVETT_ALLAPOT
        papir.alairt_file_url = fajl_url[:500]
        if not papir.file_url:
            papir.file_url = fajl_url[:500]
    else:
        # NINCS aláírt példány, de a Notion szerint a papír kiment: ez az
        # "aláírásra vár" állapot. Fontos megkülönböztetni a késztől, mert itt
        # VAN teendő - vissza kell kérni az aláírt példányt. A "Kiküldve"
        # állapot + hiányzó aláírt fájl pontosan ezt jelenti a felületen is
        # (lásd routes/megrendeloi_papirok.py alairasra_var).
        papir.allapot = "Kiküldve"


#: A számla-átvételnél ugyanez a jelölés: az így KELETKEZETT bevétel-sort erről
#: ismerjük fel újrafuttatáskor.
def _szamla_fajl(db: Session, pk: ProjectCode) -> str | None:
    """A projektkódhoz feltöltött SZÁMLA - a csatolmányokból vagy a Notionból
    örökölt URL-ből."""
    fajlok = _csatolmanyok(db, pk.id, "szamla")
    if fajlok:
        return fajlok[0].url
    return _url(pk.szamla_url)


def vedd_at_a_szamlat(db: Session, pk: ProjectCode, merleg: Atvetel) -> None:
    """A projektkód SZÁMLA-részének átvétele a bevétel-sorra.

    A Notionban a projektkód alatt ott van, mikor KELLETT volna fizetni
    (fizetési határidő), mikor fizették ki (utalás dátuma), és oda van
    feltöltve maga a számla is. Ez az adat eddig lapos mezőkben állt a
    projektkódon, a Pénzügy pedig nem tudott róla.

    ÓVATOSAN gyártunk sort: a bevételek a Notion "Bevételek" táblájából jönnek
    (lásd notion_import/importers_wave2.py). Ha már van bevétel-sor, csak a
    HIÁNYZÓ mezőit töltjük ki - egy második sor megduplázná a bevételt. Új sort
    csak akkor nyitunk, ha egyáltalán nincs bevétel, és a projektkódon van
    összeg vagy feltöltött számla."""
    szamla_url = _szamla_fajl(db, pk)
    netto = _szam(pk.netto_osszeg) or _szam(pk.szerzodes_netto_osszeg)
    van_penzugyi_adat = bool(szamla_url or pk.fizetesi_hatarido or pk.utalas_datuma or netto)
    if not van_penzugyi_adat:
        return

    sorok = list(pk.revenues or [])
    if not sorok:
        # Csak akkor nyitunk sort, ha tudjuk, MENNYIRŐL van szó: összeg nélkül
        # a bevétel-lista csak zajt kapna.
        if netto is None:
            return
        sor = Revenue(project_code_id=pk.id, netto=netto, megjegyzes=ATVETT_MEGJEGYZES)
        db.add(sor)
        sorok = [sor]
        merleg.bevetel_letrejott += 1
    else:
        merleg.bevetel_frissult += 1

    # A LEGUTÓBBI sort töltjük ki: több bevétel-sornál (részszámlák) nem lehet
    # eldönteni, melyikre vonatkozik a projektkód egyetlen dátuma - a
    # legfrissebb a legjobb tipp, és a meglévő adatot sosem írjuk felül.
    sor = sorok[-1]
    if sor.fizetes_hatarideje is None and pk.fizetesi_hatarido is not None:
        sor.fizetes_hatarideje = pk.fizetesi_hatarido
    if sor.fizetes_datuma is None and pk.utalas_datuma is not None:
        sor.fizetes_datuma = pk.utalas_datuma
    if not sor.bevetel_formaja and pk.bevetel_formaja:
        sor.bevetel_formaja = pk.bevetel_formaja
    if not sor.szamla_file_url and szamla_url:
        sor.szamla_file_url = szamla_url[:500]
        merleg.szamla_fajl_atvéve += 1
    if sor.brutto is None and netto is not None:
        # A Notion "Bruttó" mezője formula/rollup - ha nincs kézzelfogható
        # érték, a plusz-ÁFA jelölőből számolunk, ahogy a papírokon is.
        sor.brutto = round(netto * 1.27, 2) if _plusz_afa(pk.plusz_afa) else netto


def vedd_at_a_projektkodot(db: Session, pk: ProjectCode, merleg: Atvetel) -> None:
    """Egy projektkód megrendelői papírjainak átvétele. Nem commitol."""
    szerzodes_fajlok = _csatolmanyok(db, pk.id, "szerzodes")
    tig_fajlok = _csatolmanyok(db, pk.id, "tig")

    kell_szerzodes = _kell_e(
        pk.szerzodes_statusza, bool(szerzodes_fajlok), bool(pk.szerzodes_kuldes)
    )
    # A TIG-nél a projektkódon külön URL-oszlop is őrzi az aláírt papírt (a
    # Notion "TIG aláírva" / "TIG url" mezőiből) - az is fájl-bizonyíték.
    # A TIG PDF-je HÁROM helyen lehet: a projektkódhoz importált fájlok közt,
    # a "TIG aláírva" oszlopban, vagy a "TIG url" mezőben - és az utóbbi kettő
    # a régi importokból lista/objektum alakban is állhat (lásd _url).
    tig_url = _url(pk.tig_alairva_url) or _url(pk.tig_url)
    kell_tig = _kell_e(pk.tig_statusza, bool(tig_fajlok) or bool(tig_url), bool(pk.tig_kikuldve))

    if not kell_szerzodes and not kell_tig:
        merleg.kihagyott_projektkod += 1
        return

    if kell_szerzodes and not _van_sajat_papir(db, MegrendeloiSzerzodes, pk.id):
        papir = _atvett_papir(db, MegrendeloiSzerzodes, pk.id)
        uj = papir is None
        if uj:
            papir = MegrendeloiSzerzodes(project_code_id=pk.id)
            db.add(papir)
        _alkalmaz(
            papir,
            szerzodes_mezoi(pk),
            szerzodes_fajlok[0].url if szerzodes_fajlok else None,
            _kiegeszito_megjegyzes(pk),
        )
        merleg.szerzodes_letrejott += 1 if uj else 0
        merleg.szerzodes_frissult += 0 if uj else 1

    if kell_tig and not _van_sajat_papir(db, MegrendeloiTig, pk.id):
        papir = _atvett_papir(db, MegrendeloiTig, pk.id)
        uj = papir is None
        if uj:
            papir = MegrendeloiTig(project_code_id=pk.id)
            db.add(papir)
        _alkalmaz(
            papir,
            tig_mezoi(pk),
            tig_fajlok[0].url if tig_fajlok else tig_url,
            _kiegeszito_megjegyzes(pk),
        )
        merleg.tig_letrejott += 1 if uj else 0
        merleg.tig_frissult += 0 if uj else 1


def vedd_at_mindent(db: Session, project_code_ids: list[int] | None = None) -> Atvetel:
    """Az ÖSSZES (vagy a megadott) projektkód papírjainak átvétele.

    Nem commitol - a hívó dönti el, mikor zárja a tranzakciót (a migrációnak és
    az importnak más a tranzakció-kezelése)."""
    merleg = Atvetel()
    stmt = select(ProjectCode)
    if project_code_ids is not None:
        if not project_code_ids:
            return merleg
        stmt = stmt.where(ProjectCode.id.in_(project_code_ids))
    else:
        # Teljes futáskor a keretszerződések hiányzó ügyfél-kapcsolatát is
        # pótoljuk: enélkül az ügyfél nélkül importált keret sosem fedne le
        # egyetlen projektet sem.
        merleg.keret_ugyfelhez_kotve = kosd_ugyfelhez_a_kereteket(db)
    for pk in db.scalars(stmt.order_by(ProjectCode.id)):
        vedd_at_a_projektkodot(db, pk, merleg)
        vedd_at_a_szamlat(db, pk, merleg)
    return merleg
