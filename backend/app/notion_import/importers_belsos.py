"""A Notionban vezetett BELSŐS TIG nyilvántartás áthozása.

Notionban egy belsős munkatárs oldalán van egy "Belsős TIG" szekció, benne a
visszamenőleges havi TIG-ekkel: a generált TIG (Drive-link a "TIG aláírva"
mezőben), a kiállított számla (feltöltött fájl), a hónap nettó/bruttó összege,
a számla fizetési határideje, az utalás napja, és a TIG teljesítési/keltezési
dátuma. A hozzájuk tartozó extrák külön táblában ("Belsős extra kiadások")
vannak.

Ez az importer ezt a szerkezetet képezi le a mi modellünkre:

    Notion                              HYPE OS
    ────────────────────────────────────────────────────────────────────────
    Belsős TIG (egy sor = egy hónap)  -> InternalPerformanceCertificate
      TIG aláírva (Drive link/fájl)   ->   file_url (Notion-fájl esetén R2-re)
      Számla (feltöltött fájl)        ->   InternalPerformanceCertificateInvoice
      Nettó / Bruttó                  ->   netto_osszeg (+ plusz_afa, ha eltér)
      Fizetési határidő               ->   fizetesi_hatarido
      Utalás dátuma                   ->   utalas_datuma (+ szamla_kifizetve)
      Teljesítés / Keltezés           ->   teljesites_datuma / keltezes
    Belsős extra kiadások            -> EmployeeMonthlyItem (extra/levonandó)

Három fázisban fut, és a sorrend számít:
  1. a TIG-ek (ezekre hivatkozhatnak az extrák),
  2. az extrák (a hónapjukat a TIG-relation, annak híján a dátumuk adja),
  3. az alapbér-maradék: a hónap TIG-összege mínusz az extrák - enélkül a
     régi hónapok bontása üres lenne az összeg mellett (lásd _alapber_potlas).

Miért ilyen védekező a mezőnév-kezelés: a Belsős TIG tábla ID-ja nincs
rögzítve a database_ids.py-ban (a discovery futtatásakor nem volt megosztva az
integrációval), és az öt éve élő tábla mezőnevei sem garantáltak. Ezért a
táblát NÉV alapján keressük meg, a mezőket pedig névjelöltek listájával - ha
egy név mégis más, egy jelölt hozzáírása elég, nem kell újraírni az importert.
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.services.hu_szoveg import ekezet_nelkul
from app.models.employee_monthly_item import EmployeeMonthlyItem
from app.models.internal_performance_certificate import (
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.models.notion_import import NotionImportMap
from app.notion_import import database_ids as db_ids
from app.notion_import import files
from app.notion_import.client import NotionClient, as_date, database_title, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, safe_upsert
from app.services import document_storage
from app.services.hu_datum import HONAP_NEVEK, elozo_honap, ev_honap_szoveg
from app.services.portal_storage import R2NotConfiguredError

# A Notion-tábla neve. A HYPE workspace-ben ez a tábla egyszerűen "Belsős"
# (a belsősök havi TIG-jei és számlái vannak benne, nem munkatárs-törzsadat -
# a crew-directory a "Külsős és belsős"). Kisbetűsítve, ékezet nélkül
# hasonlítunk, PONTOS egyezéssel: így a "kulsos es belsos" nem téveszthető
# össze vele.
BELSOS_TIG_TABLA_NEVEK = ("belsos", "belsos tig", "belsos tigek", "belsos havi tig", "belsos tig-ek")

# Mezőnév-jelöltek. Az ELSŐ nem üres érték nyer (lásd _mezo), ezért a
# jelöltek sorrendje SZÁMÍT: elöl a HYPE "Belsős" táblájának tényleges
# mezőnevei (2026-08-08-i ellenőrzés), utánuk a régebbi/variáns nevek.
NEV_SZEMELY = ("Belsős", "Belsos", "Személy", "Munkatárs", "Külsős és belsős", "👥 Külsős és belsős", "Név")
NEV_TIG_FAJL = ("TIG aláírva", "TIG aláírás", "Aláírt TIG", "TIG", "TIG link")
NEV_SZAMLA = ("Számla", "Kiállított számla", "Számla pdf", "Számla fájl")
#: Alkalmazotti (nem számlás) elszámolásnál a számla helyett ez a papír van.
NEV_FIZ_JEGYZEK = ("Fizetési jegyzék", "Fizetesi jegyzek", "Bérjegyzék")
# FONTOS a sorrend: a "Nettó összeg" a kézzel bevitt SZÁM (erről szól a
# számla), a "Nettó" viszont egy FORMULA ugyanabban a táblában, ami az
# extrákkal együtt számol. Ha a formula nyerne, más összeg kerülne a TIG-re,
# mint ami a papíron van.
NEV_NETTO = ("Nettó összeg", "Netto osszeg", "Nettó", "Netto")
NEV_BRUTTO = ("Bruttó összeg", "Brutto osszeg", "Bruttó", "Brutto")
#: A "+ ÁFA" jelölés select mezőben - ez egyértelműbb, mint a bruttó/nettó
#: arányból következtetni.
NEV_PLUSZ_AFA = ("Plusz ÁFA", "Plusz AFA", "+ ÁFA", "ÁFA")
NEV_FIZ_HATARIDO = ("Fizetési határidő", "Fizetesi hatarido", "Fizetési határidő dátuma")
NEV_UTALAS = ("Utalás időpontja", "Utalás dátuma", "Utalas datuma", "Utalás", "Kifizetés dátuma")
NEV_TELJESITES = ("Teljesítési idő", "Teljesítés dátuma", "Teljesítés", "Teljesites datuma", "Teljesítés ideje")
NEV_KELTEZES = ("Keltezési idő", "Keltezés", "Keltezés dátuma", "Kelt", "Keltezes")
NEV_ALLAPOT = ("Állapot", "Státusz", "Status", "Statusz")
#: A SZÁMLA külön státusza - ebből derül ki, mit fizettünk már ki.
NEV_SZAMLA_ALLAPOT = ("Számla státusza", "Szamla statusza", "Számla állapota")
NEV_MEGBIZAS_TARGYA = ("Megbízás Tárgya", "Megbízás tárgya", "Megbizas targya")
NEV_MEGJEGYZES = ("Megjegyzés", "Megjegyzes", "Comment")

#: A Notion "Számla státusza" értékei, amik KIFIZETETT állapotot jelentenek.
#: Kisbetűsítve, ékezet nélkül hasonlítunk, RÉSZLETRE - a teljes szöveg
#: ("Alkalmazott (Fizetve és fizetési jegyzék feltöltve)") túl törékeny lenne.
KIFIZETETT_SZAMLA_JELEK = ("kifizettuk", "fizetve")

#: A Notion "Állapot" értékei, amik LEZÁRT TIG-et jelentenek. Nálunk ez a
#: "Kiküldve" (lásd routes/internal_performance_certificates.py
#: FINALIZED_STATUSES) - a Notion két kész-állapota egyaránt ezt jelenti.
NOTION_ALLAPOT_MEGFELELTETES = {
    "kesz feltoltve": "Kiküldve",
    "elkeszult es kikuldve": "Kiküldve",
    "nincs elkezdve": "Készítés alatt",
}
NEV_HONAP = ("Hónap", "Melyik hónap", "Elszámolás hónapja", "Honap")

# A "Belsős extra kiadások" tábla mezői (ezeket a discovery már kiírta, lásd
# importers_wave2.import_expenses - ugyanezt a táblát Expense-ként is bevisszük).
NEV_EXTRA_MEGNEVEZES = ("Megnevezés", "Név", "Leírás", "Kiadás megnevezése")
NEV_EXTRA_OSSZEG = ("Összeg", "Kiadás összege", "Bruttó összeg", "Bruttó", "Nettó összeg", "Nettó")
NEV_EXTRA_DATUM = ("Kiadás időpontja", "Dátum", "Kiadás dátuma", "Időpont")
NEV_EXTRA_TIG = ("Belsős TIG", "Belsős Havi TIG", "Belsős", "TIG")
NEV_EXTRA_SZEMELY = ("Személy", "Belsős", "Munkatárs")
NEV_EXTRA_PROJEKTKOD = ("Projektkód", "HYPE ADMIN projektkódok", "Projekt")

# Ha a mezőnév egyik jelöltre sem illik, ezekre a KULCSSZAVAKRA is ránézünk a
# mező nevében (öt éve élő táblában a "Túlóra összege"-szerű nevek gyakoriak).
EXTRA_OSSZEG_KULCSSZAVAK = ("osszeg", "koltseg", "ara", "ar ", "brutto", "netto")
EXTRA_MEGNEVEZES_KULCSSZAVAK = ("megnevez", "leiras", "nev", "tetel", "mire")

MAX_MEGNEVEZES = 255


def _ekezet_nelkul(szoveg: str) -> str:
    return ekezet_nelkul(szoveg)


HONAP_NEVEK_EKEZET_NELKUL = tuple(_ekezet_nelkul(nev) for nev in HONAP_NEVEK)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = next((v for v in value if v), None)
    if value is None:
        return None
    szoveg = str(value).strip()
    return szoveg or None


def _szam(value: Any) -> float | None:
    """Notion number/formula/rollup -> float. A szövegként vezetett összeget is
    megpróbálja (öt éve élő táblában van ilyen), a szóközöket és a 'Ft'-ot
    eldobva."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        return _szam(next((v for v in value if v is not None), None))
    szoveg = str(value).replace("\xa0", "").replace(" ", "").replace("Ft", "").replace(",", ".")
    try:
        return float(szoveg)
    except ValueError:
        return None


def _mezo(props: dict, nevek: tuple[str, ...]) -> Any:
    """Az első NEM ÜRES érték a névjelöltek közül."""
    for nev in nevek:
        if nev in props:
            ertek = props[nev]
            if ertek not in (None, "", []):
                return ertek
    return None


def _kulcsszo_szerint(props: dict, kulcsszavak: tuple[str, ...], *, szam: bool) -> Any:
    """Érték keresése a mező NEVÉBEN szereplő kulcsszó alapján.

    Ez a legvégső mentőöv: ha egy öt éve élő táblában az összeg oszlopa épp
    "Túlóra összege", a nevekre épülő jelölt-lista nem találná meg, pedig az
    adat ott van. `szam=True` esetén csak számot fogadunk el (egy "Összeg
    megjegyzés" szövegmező nem lehet az összeg)."""
    for nev, ertek in props.items():
        nev_kulcs = _ekezet_nelkul(nev)
        if not any(k in nev_kulcs for k in kulcsszavak):
            continue
        if szam:
            if _szam(ertek) is not None:
                return ertek
        elif _text(ertek):
            return _text(ertek)
    return None


def _relaciobol(db: Session, props: dict, nevek: tuple[str, ...], entity_type: str) -> int | None:
    """Relation mezőből feloldott azonosító: előbb a névre ismert mezők, aztán
    BÁRMELY relation, ami a keresett entitásra oldható fel. Az öt éve élő
    táblákban a mezőnevek nem egységesek, a relation célja viszont az."""
    for nev in nevek:
        ertek = props.get(nev)
        if isinstance(ertek, list) and ertek:
            talalat = resolve_relation_id(db, entity_type, ertek)
            if talalat is not None:
                return talalat
    for ertek in props.values():
        if isinstance(ertek, list) and ertek and all(isinstance(v, str) for v in ertek):
            talalat = resolve_relation_id(db, entity_type, ertek)
            if talalat is not None:
                return talalat
    return None


def _fajl_urlek(ertek: Any) -> list[str]:
    if ertek is None:
        return []
    if isinstance(ertek, str):
        return [ertek]
    if isinstance(ertek, list):
        return [u for u in ertek if isinstance(u, str) and u]
    return []


def _kifizetve(props: dict, utalas: date | None) -> bool:
    """Ki van-e már fizetve ez a hónap?

    Két, egymást erősítő jel van a Notionban, és MINDKETTŐ elég önmagában:

    - az "Utalás időpontja" ki van töltve (megtörtént a tényleges utalás),
    - a "Számla státusza" kifizetettre van állítva ("Kifizettük és számla
      feltöltve", illetve alkalmazottnál "Alkalmazott (Fizetve és fizetési
      jegyzék feltöltve)").

    Azért nem elég az utalás dátuma: a régi sorokon néha csak a státusz van
    kitöltve. És azért nem elég a státusz: a most kifizetett soroknál előbb
    kerül be a dátum."""
    if utalas is not None:
        return True
    statusz = _ekezet_nelkul(_text(_mezo(props, NEV_SZAMLA_ALLAPOT)) or "")
    return any(jel in statusz for jel in KIFIZETETT_SZAMLA_JELEK)


def _allapot(props: dict, netto: float | None, teljesites: date | None) -> str | None:
    """A Notion "Állapot" a mi állapot-szótárunkra fordítva.

    A Notion "Kész feltöltve" / "Elkészült és kiküldve" nálunk egyaránt
    "Kiküldve": a TIG elkészült és kiment, nincs vele több teendő (lásd
    routes/internal_performance_certificates.py FINALIZED_STATUSES). Ha ezt
    nyersen átvennénk, a régi, lezárt hónapok mind visszakerülnének a
    "készítendő" listára."""
    nyers = _text(_mezo(props, NEV_ALLAPOT))
    if nyers:
        forditott = NOTION_ALLAPOT_MEGFELELTETES.get(_ekezet_nelkul(nyers))
        if forditott:
            return forditott
        return nyers
    # Állapot nélküli régi sor: ha van összeg vagy teljesítés, lezártnak
    # vesszük - különben évekkel később "hiányzóként" jönne vissza.
    return "Kiküldve" if (netto or teljesites) else None


def _plusz_afa(props: dict, netto: float | None, brutto: float | None) -> bool:
    """Kell-e ÁFA-t felszámolni?

    Ha a soron OTT VAN a "Plusz ÁFA" jelölő mező, az dönt - akkor is, ha üres:
    az üres jelölő azt jelenti, hogy nincs ÁFA. A bruttó/nettó arány csak
    akkor tartalék, ha ilyen mező egyáltalán nincs a táblában (régebbi vagy
    másik szerkezetű nyilvántartás). Fordítva hibás lenne: a "Bruttó" a
    Notionban FORMULA, ami az extrákkal is számolhat, tehát simán nagyobb a
    nettónál ÁFA nélkül is."""
    for nev in NEV_PLUSZ_AFA:
        if nev in props:
            return "afa" in _ekezet_nelkul(_text(props[nev]) or "")
    return bool(netto and brutto and brutto > netto * 1.05)


def belsos_tig_database_id(client: NotionClient) -> str | None:
    """A Belsős TIG tábla ID-ja. Ha a database_ids.py-ban rögzítve van, azt
    használjuk; különben NÉV alapján keressük meg az integrációval megosztott
    táblák között."""
    rogzitett = getattr(db_ids, "BELSOS_TIG", None)
    if rogzitett:
        return rogzitett
    for database in client.search_databases():
        if _ekezet_nelkul(database_title(database)) in BELSOS_TIG_TABLA_NEVEK:
            return database["id"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. fázis: a havi TIG-ek
# ─────────────────────────────────────────────────────────────────────────────


def _page_cim(page: dict, props: dict) -> str | None:
    """A Notion-sor címe (a title típusú property értéke). Azért a típusból és
    nem névből, mert a HYPE tábláiban a cím-oszlop hol "Name", hol "Név"."""
    for nev, prop in page.get("properties", {}).items():
        if prop.get("type") == "title":
            return _text(props.get(nev))
    return None


def visszafele_index(db: Session) -> dict[str, int]:
    """Notion TIG-oldal ID -> a mi munkatárs-azonosítónk, a MUNKATÁRS felől.

    A "Külsős és belsős" tábla "Belsős TIG" relation-je az importkor
    bekerült a munkatárs `belsos_tig_notion_ids` mezőjébe. Ez a legmegbízhatóbb
    kapcsolat: akkor is megvan, ha a TIG-sorban magában nincs (vagy más néven
    van) a visszamutató relation - és pont ez okozta, hogy sok embernél nem
    jött át semmi."""
    index: dict[str, int] = {}
    for employee_id, ids in db.execute(
        select(Employee.id, Employee.belsos_tig_notion_ids).where(
            Employee.belsos_tig_notion_ids.is_not(None)
        )
    ):
        if isinstance(ids, list):
            for page_id in ids:
                if isinstance(page_id, str) and page_id:
                    index.setdefault(page_id, employee_id)
    return index


def _nev_szerint(db: Session, nyers: str | None) -> int | None:
    """Munkatárs a NEVE alapján. Csak akkor ad találatot, ha pontosan egy
    emberre illik - egy névrokon miatt nem kerülhet valaki más TIG-je máshoz.

    A cím gyakran "Kovács Béla - 2026. május" vagy "Kovács Béla 2026.05"
    alakú, ezért a dátumszerű farkot levágjuk."""
    if not nyers:
        return None
    nev = re.split(r"\s+[-–—]\s+|\s*\d{4}[.\s]", nyers)[0].strip(" -–—.")
    if len(nev) < 4:
        return None
    talalatok = db.scalars(select(Employee).where(Employee.full_name.ilike(nev))).all()
    if len(talalatok) == 1:
        return talalatok[0].id
    # Ékezet/kötőjel eltérésre is adunk egy esélyt (a Notionban gyakori az
    # ékezet nélküli írásmód) - továbbra is csak egyértelmű találatnál.
    kulcs = _ekezet_nelkul(nev)
    egyezok = [e for e in db.scalars(select(Employee)).all() if _ekezet_nelkul(e.full_name) == kulcs]
    return egyezok[0].id if len(egyezok) == 1 else None


def _employee_id(db: Session, page_id: str, props: dict, page_cim: str | None, index: dict[str, int]) -> int | None:
    """A TIG munkatársa, négy forrásból - a legmegbízhatóbbtól haladva:

    1. a munkatárs felőli relation (visszafele_index),
    2. a TIG-sor névre ismert személy-relation mezői,
    3. BÁRMELY relation mezője, ami munkatársra oldható fel (öt éve élő
       táblában a mező neve bármi lehet: "Kinek", "Belsős munkatárs"…),
    4. végül a sor címe név szerint."""
    talalat = index.get(page_id)
    if talalat is not None:
        return talalat

    talalat = _relaciobol(db, props, NEV_SZEMELY, "Employee")
    if talalat is not None:
        return talalat

    # A személy neve szövegmezőben is állhat, nem csak a címben.
    for jelolt in (page_cim, *(_text(props.get(nev)) for nev in NEV_SZEMELY)):
        talalat = _nev_szerint(db, jelolt)
        if talalat is not None:
            return talalat
    return None


def _honap_cimbol(cim: str | None) -> tuple[int, int] | None:
    """"Kovács Béla - 2026. május" / "2026.05" -> (2026, 5).

    A címben a hónap ADOTT (nem következtetni kell rá), ezért jó mentőöv
    azoknál a soroknál, ahol se hónap-mező, se teljesítési dátum nincs."""
    if not cim:
        return None
    szoveg = _ekezet_nelkul(cim)
    ev_talalat = re.search(r"(20\d{2})", szoveg)
    if not ev_talalat:
        return None
    ev = int(ev_talalat.group(1))
    maradek = szoveg[ev_talalat.end() :]
    for i, nev in enumerate(HONAP_NEVEK_EKEZET_NELKUL, start=1):
        if nev in maradek:
            return ev, i
    szam_talalat = re.search(r"[.\s/-]\s*(0?[1-9]|1[0-2])(?![0-9])", maradek)
    if szam_talalat:
        return ev, int(szam_talalat.group(1))
    return None


def _honap(props: dict, cim: str | None, teljesites: date | None, keltezes: date | None) -> tuple[int, int] | None:
    """Melyik hónap TIG-je ez.

    A rendszer szabálya: a hónapot a TELJESÍTÉS dátuma adja, és mindig az azt
    MEGELŐZŐ hónapot jelenti (2026.07.20-i teljesítés = a 2026. JÚNIUSI TIG) -
    lásd services/hu_datum.elozo_honap. Ugyanez áll a fizetési határidőre és
    az utalás napjára: azok is a hónapot KÖVETŐ hónapra esnek.

    A DÁTUMOK erősebbek a kimondott hónapnál. A Notionban a lapok címe (és
    sokszor a hónap-mező is) azt a hónapot viseli, AMIKOR a TIG készült - a
    júliusi lapon a júniusi elszámolás van -, tehát a cím szó szerinti
    átvétele egy hónappal elcsúsztatná az egészet. A kimondott hónap ezért
    csak akkor dönt, ha egyetlen dátum sincs a soron.

    Inkább egy jó eséllyel helyes hónap, mint egy kihagyott sor - a hónap a
    felületen bármikor javítható."""
    if teljesites is not None:
        return elozo_honap(teljesites)
    for nev in (NEV_FIZ_HATARIDO, NEV_UTALAS):
        datum = as_date(_mezo(props, nev))
        if datum is not None:
            return elozo_honap(datum)
    if keltezes is not None:
        return elozo_honap(keltezes)
    explicit = as_date(_mezo(props, NEV_HONAP))
    if explicit is not None:
        return explicit.year, explicit.month
    return _honap_cimbol(cim)


def _tig_dokumentum(db: Session, props: dict, tig: InternalPerformanceCertificate, result: ImportResult) -> None:
    """A "TIG aláírva" mező: Drive-link esetén marad a link (nem jár lejárattal,
    és nem is a mi tárhelyünk), Notionban TÁROLT fájl esetén átemeljük az
    R2-re - különben a link kb. egy óra múlva halott lenne."""
    urlek = _fajl_urlek(_mezo(props, NEV_TIG_FAJL))
    if not urlek:
        return
    url = urlek[0]
    if files.notion_fajl_e(url):
        uj = files.atemel(
            db,
            url,
            entity_type="employee",
            entity_id=tig.employee_id,
            kategoria="tig",
            log=result.file_errors.append,
        )
        if uj and uj != url:
            result.files_copied += 1
        url = uj or url
    tig.file_url = url[:500]


def _tig_szamlai(db: Session, props: dict, tig: InternalPerformanceCertificate, result: ImportResult) -> None:
    """A "Számla" mezőbe feltöltött kiállított számlák átemelése a TIG saját
    számla-táblájába (nem a generikus csatolmányok közé: a Belsős TIG felülete
    innen listázza és innen tölti le őket).

    Az ALKALMAZOTTI elszámolásnál nincs számla, hanem "Fizetési jegyzék" -
    az ugyanide kerül: a felületen ugyanaz a szerepe (ez a papír igazolja a
    kifizetést), és enélkül azoknál a hónapoknál üresen maradna a számla-oszlop.

    Idempotens a notion_forras-on keresztül: egy újrafuttatás nem tölti le és
    nem duplikálja ugyanazt a fájlt."""
    urlek = [
        *_fajl_urlek(_mezo(props, NEV_SZAMLA)),
        *_fajl_urlek(_mezo(props, NEV_FIZ_JEGYZEK)),
    ]
    for url in urlek:
        if not files.notion_fajl_e(url):
            continue
        forras = files.forras_kulcs(url)
        letezik = db.scalar(
            select(InternalPerformanceCertificateInvoice.id).where(
                InternalPerformanceCertificateInvoice.certificate_id == tig.id,
                InternalPerformanceCertificateInvoice.notion_forras == forras,
            )
        )
        if letezik is not None:
            continue
        if not document_storage.is_configured():
            result.file_errors.append(f"R2 nincs beállítva - a számla kimaradt: {files.fajlnev(url)}")
            continue
        try:
            # Savepoint: a számla-sort a feltöltés ELŐTT vesszük fel (az id-ból
            # képződik a tárhely-kulcs), így egy elhasalt feltöltés ne hagyjon
            # üres kulcsú, féllábú sort a tranzakcióban.
            with db.begin_nested():
                adat, content_type = files.letolt(url)
                nev = files.fajlnev(url)
                szamla = InternalPerformanceCertificateInvoice(
                    certificate_id=tig.id,
                    filename=nev,
                    content_type=content_type,
                    storage_key="",
                    url="",
                    notion_forras=forras,
                )
                db.add(szamla)
                db.flush()
                kulcs = (
                    f"belsos-tig-szamla/{tig.employee_id}/"
                    f"{tig.ev}-{tig.honap:02d}-{szamla.id}{os.path.splitext(nev)[1]}"
                )
                szamla.url = document_storage.upload_bytes(
                    adat, kulcs, content_type or "application/octet-stream"
                )
                szamla.storage_key = kulcs
                db.flush()
        except (httpx.HTTPError, ValueError, R2NotConfiguredError) as exc:
            result.file_errors.append(f"Számla kimaradt ({files.fajlnev(url)}): {type(exc).__name__}: {exc}")
            continue
        result.files_copied += 1


def _utkozik_meglevovel(db: Session, page_id: str, employee_id: int, ev: int, honap: int) -> bool:
    """Van-e már TIG erre a hónapra, ami NEM ebből a Notion-sorból származik.

    Egy emberhez egy hónapban egyetlen TIG tartozhat. Ha a hónap TIG-jét már a
    rendszerben elkészítették (saját összeggel, dokumentummal, esetleg ki is
    küldve), akkor egy import nem írhatja felül egy évekkel korábbi Notion-sor
    adataival - inkább kihagyjuk, és megmondjuk, miért."""
    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == page_id))
    letezo_id = db.scalar(
        select(InternalPerformanceCertificate.id).where(
            InternalPerformanceCertificate.employee_id == employee_id,
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
        )
    )
    if letezo_id is None:
        return False
    # Ha ez a Notion-sor korábban épp EZT a rekordot hozta létre, nincs ütközés:
    # a frissítés a saját adatát írja felül.
    return mapping is None or mapping.entity_id != letezo_id


def _tig_extrai(props: dict, extra_idk: set[str]) -> list[str]:
    """A TIG-hez kapcsolt "Belsős extra kiadások" sorok Notion-ID-i.

    A kapcsolat a TIG FELŐL van (relation), és ez a mérvadó: ezekből az
    extrákból áll össze a hónap összege, amiről a számla is szól. Nem a mező
    NEVÉRE szűrünk, hanem arra, hogy a relation célja tényleg az extra
    kiadások táblájába mutat-e - így akárhogy is hívják azt a mezőt, megvan."""
    talalatok: list[str] = []
    for ertek in props.values():
        if not isinstance(ertek, list):
            continue
        egyezo = [v for v in ertek if isinstance(v, str) and v in extra_idk]
        talalatok.extend(egyezo)
    # Sorrendtartó egyedivé tétel (ugyanaz a sor több mezőn is beeshet).
    return list(dict.fromkeys(talalatok))


def _import_tigek(
    client: NotionClient,
    db: Session,
    result: ImportResult,
    extra_idk: set[str],
    hozzarendeles: dict[str, tuple[int, int, int]],
) -> None:
    database_id = belsos_tig_database_id(client)
    if database_id is None:
        result.errors.append(
            "A 'Belsős TIG' Notion tábla nem található. Oszd meg az integrációval "
            "(Notion: '...' -> Connections), vagy vedd fel az ID-ját a "
            "notion_import/database_ids.py BELSOS_TIG konstansába."
        )
        return

    index = visszafele_index(db)
    for page in client.query_database(database_id):
        props = extract_properties(page, client)
        cim = _page_cim(page, props)
        employee_id = _employee_id(db, page["id"], props, cim, index)
        if employee_id is None:
            result.skipped += 1
            result.errors.append(f"Belsős TIG '{cim or page['id']}': nem azonosítható a munkatárs, kihagyva")
            continue

        teljesites = as_date(_mezo(props, NEV_TELJESITES))
        keltezes = as_date(_mezo(props, NEV_KELTEZES))
        honap_par = _honap(props, cim, teljesites, keltezes)
        if honap_par is None:
            result.skipped += 1
            result.errors.append(
                f"Belsős TIG '{cim or page['id']}': nincs teljesítési/keltezési dátum, "
                "így nem eldönthető, melyik hónapé - kihagyva"
            )
            continue
        ev, honap = honap_par

        if _utkozik_meglevovel(db, page["id"], employee_id, ev, honap):
            result.skipped += 1
            result.errors.append(
                f"Belsős TIG '{cim or page['id']}' ({ev_honap_szoveg(ev, honap)}): erre a hónapra "
                "MÁR VAN TIG a rendszerben, ezért a Notion-sort nem hoztuk át (nem írjuk felül a "
                "rendszerben készültet). Ha mégis a Notion adata a jó, töröld a meglévőt és futtasd újra."
            )
            continue

        netto = _szam(_mezo(props, NEV_NETTO))
        brutto = _szam(_mezo(props, NEV_BRUTTO))
        # A bruttót nem tároljuk külön: nálunk a nettóból és a plusz_afa
        # jelölésből SZÁMOLÓDIK (lásd schemas InternalPerformanceCertificateRead).
        plusz_afa = _plusz_afa(props, netto, brutto)
        utalas = as_date(_mezo(props, NEV_UTALAS))

        tig = safe_upsert(
            db,
            result,
            InternalPerformanceCertificate,
            "InternalPerformanceCertificate",
            page["id"],
            {
                "employee_id": employee_id,
                "ev": ev,
                "honap": honap,
                "allapot": _allapot(props, netto, teljesites),
                "megbizas_targya": _text(_mezo(props, NEV_MEGBIZAS_TARGYA)),
                "megjegyzes": (_text(_mezo(props, NEV_MEGJEGYZES)) or None),
                "netto_osszeg": netto if netto is not None else brutto,
                "plusz_afa": plusz_afa,
                "teljesites_datuma": teljesites,
                "keltezes": keltezes,
                "fizetesi_hatarido": as_date(_mezo(props, NEV_FIZ_HATARIDO)),
                "utalas_datuma": utalas,
                # A kifizetés tényét az utalás dátuma VAGY a számla státusza
                # adja (lásd _kifizetve). Expense sort SZÁNDÉKOSAN nem hozunk
                # létre hozzá (ellentétben a felületi "kifizetve" gombbal): a
                # régi kifizetések a Notion 'Kiadások' tábláján keresztül már
                # bejönnek, egy második sor duplán terhelné a pénzügyi
                # kimutatásokat.
                "szamla_kifizetve": _kifizetve(props, utalas),
            },
            label=f"Belsős TIG '{cim or ''}' ({ev_honap_szoveg(ev, honap)})",
        )
        if tig is None:
            continue
        _tig_dokumentum(db, props, tig, result)
        _tig_szamlai(db, props, tig, result)
        # A hónaphoz kapcsolt extrák innen kapják meg, KIHEZ és MELYIK
        # hónaphoz tartoznak - az extra-sorban ez az információ sokszor nincs
        # is benne, csak ez a relation köti össze őket.
        for extra_id in _tig_extrai(props, extra_idk):
            hozzarendeles.setdefault(extra_id, (employee_id, ev, honap))


# ─────────────────────────────────────────────────────────────────────────────
# 2. fázis: a havi extrák
# ─────────────────────────────────────────────────────────────────────────────


def _tetel_honapja(db: Session, props: dict, datum: date | None) -> tuple[int, int] | None:
    """Melyik havi elszámolásba tartozik az extra. Ha a Notion-sor a TIG-hez
    van kötve, az dönt (az a szándék); különben a saját dátumának hónapja."""
    for nev in NEV_EXTRA_TIG:
        ertek = props.get(nev)
        if isinstance(ertek, list) and ertek:
            tig_id = resolve_relation_id(db, "InternalPerformanceCertificate", ertek)
            if tig_id is not None:
                tig = db.get(InternalPerformanceCertificate, tig_id)
                if tig is not None:
                    return tig.ev, tig.honap
    return (datum.year, datum.month) if datum else None


def _import_extrak(
    db: Session,
    result: ImportResult,
    oldalak: list[tuple[dict, dict]],
    hozzarendeles: dict[str, tuple[int, int, int]],
) -> None:
    """A 'Belsős extra kiadások' tábla havi tételként.

    A hovatartozás elsődleges forrása a TIG felőli relation (`hozzarendeles`):
    Notionban a hónap TIG-je sorolja fel a hozzáadódó extrákat, és pont
    ezekből jön ki az az összeg, amiről az adott ember a számlát írta. Csak ha
    egy extra nincs egyetlen TIG-hez sem kötve, akkor próbáljuk a saját
    személy-relationjéből és dátumából elhelyezni.

    Ugyanez a tábla Expense-ként IS bejön (importers_wave2.import_expenses) -
    ott a pénzügyi kimutatás miatt, itt azért, hogy a munkatárs havi
    elszámolásában lássuk, miből állt össze az összeg. A kettőt összekötjük
    (expense_id), hogy a felületen egyszer szerepeljen, ne kétszer."""
    for page, props in oldalak:
        megnevezes = (
            _text(_mezo(props, NEV_EXTRA_MEGNEVEZES))
            or _page_cim(page, props)
            or _kulcsszo_szerint(props, EXTRA_MEGNEVEZES_KULCSSZAVAK, szam=False)
            or "Extra kiadás"
        )
        osszeg = _szam(_mezo(props, NEV_EXTRA_OSSZEG))
        if osszeg is None:
            osszeg = _szam(_kulcsszo_szerint(props, EXTRA_OSSZEG_KULCSSZAVAK, szam=True))
        if osszeg is None or osszeg == 0:
            result.skipped += 1
            continue

        datum = as_date(_mezo(props, NEV_EXTRA_DATUM))
        helye = hozzarendeles.get(page["id"])
        if helye is not None:
            employee_id, ev, honap = helye
        else:
            employee_id = _relaciobol(db, props, NEV_EXTRA_SZEMELY, "Employee")
            honap_par = _tetel_honapja(db, props, datum)
            if employee_id is None or honap_par is None:
                result.skipped += 1
                result.errors.append(
                    f"Belsős extra '{megnevezes}': nincs egyetlen Belsős TIG-hez sem kötve, és a "
                    "sorból sem derül ki, kihez/melyik hónaphoz tartozik - kihagyva"
                )
                continue
            ev, honap = honap_par

        # A negatív összeg levonás. Nálunk a levonandó tétel összege POZITÍV,
        # az előjelet a típus adja (lásd models/employee_monthly_item.py).
        tipus = "levonando" if osszeg < 0 else "extra"

        project_code_id = _relaciobol(db, props, NEV_EXTRA_PROJEKTKOD, "ProjectCode")

        mezok = {
            "employee_id": employee_id,
            "ev": ev,
            "honap": honap,
            "tipus": tipus,
            "megnevezes": megnevezes[:MAX_MEGNEVEZES],
            "osszeg": abs(osszeg),
            "project_code_id": project_code_id,
            "datum": datum,
            # A vele azonos pénzügyi kiadás-sor (ugyanabból a Notion-oldalból).
            "expense_id": resolve_relation_id(db, "Expense", [page["id"]]),
        }
        try:
            with db.begin_nested():
                tetel = db.scalar(
                    select(EmployeeMonthlyItem).where(EmployeeMonthlyItem.notion_page_id == page["id"])
                )
                if tetel is None:
                    db.add(EmployeeMonthlyItem(notion_page_id=page["id"], **mezok))
                    db.flush()
                    result.created += 1
                else:
                    for kulcs, ertek in mezok.items():
                        setattr(tetel, kulcs, ertek)
                    db.flush()
                    result.updated += 1
        except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
            result.errors.append(f"Belsős extra '{megnevezes}': {type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. fázis: alapbér-maradék
# ─────────────────────────────────────────────────────────────────────────────


def _alapber_potlas(db: Session, result: ImportResult) -> None:
    """A régi hónapok bontásának kiegészítése alapbér-tétellel.

    A Notionban a TIG összege egyetlen szám volt, az extrák külön táblában
    éltek; nálunk a hónap összege a TÉTELEKBŐL áll össze. Ha az áthozott
    hónapnál csak az extrák lennének meg, a bontás nem adná ki az összeget -
    a nézet egy 800 000 Ft-os TIG mellett 30 000 Ft extrát mutatna, mintha a
    többi eltűnt volna.

    Ezért a különbözetet (TIG nettó - extrák + levonások) alapbér-tételként
    vesszük fel. Ez pontosan az az összeg, amit akkoriban alapbérként
    kifizettünk: a TIG összege ebből és az extrákból állt össze."""
    tigek = db.scalars(
        select(InternalPerformanceCertificate).where(
            InternalPerformanceCertificate.netto_osszeg.is_not(None)
        )
    ).all()
    for tig in tigek:
        tetelek = db.scalars(
            select(EmployeeMonthlyItem).where(
                EmployeeMonthlyItem.employee_id == tig.employee_id,
                EmployeeMonthlyItem.ev == tig.ev,
                EmployeeMonthlyItem.honap == tig.honap,
            )
        ).all()
        if not any(t.notion_page_id for t in tetelek):
            # Ehhez a hónaphoz nem hoztunk át semmit Notionból - nem a mi
            # dolgunk kitalálni a bontását.
            continue
        kezi_alapber = [t for t in tetelek if t.tipus == "alapber" and not t.notion_page_id]
        if kezi_alapber:
            # Kézzel felvitt alapbér van: azt nem írjuk felül.
            continue
        extrak = sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "extra")
        levonasok = sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "levonando")
        maradek = round(float(tig.netto_osszeg) - extrak + levonasok, 2)
        if maradek <= 0:
            continue

        kulcs = f"{tig.id}-alapber-notion"
        meglevo = next((t for t in tetelek if t.notion_page_id == kulcs), None)
        try:
            with db.begin_nested():
                if meglevo is None:
                    db.add(
                        EmployeeMonthlyItem(
                            notion_page_id=kulcs,
                            employee_id=tig.employee_id,
                            ev=tig.ev,
                            honap=tig.honap,
                            tipus="alapber",
                            megnevezes="Alapbér",
                            osszeg=maradek,
                            megjegyzes="Notion importból: a havi TIG összege és az extrák különbözete",
                        )
                    )
                else:
                    meglevo.osszeg = maradek
                db.flush()
        except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
            result.errors.append(
                f"Alapbér-tétel ({ev_honap_szoveg(tig.ev, tig.honap)}, employee_id={tig.employee_id}): "
                f"{type(exc).__name__}: {exc}"
            )


def import_belsos_tig(client: NotionClient, db: Session) -> ImportResult:
    """Belsős TIG + a hozzá tartozó havi extrák + alapbér-maradék.

    A sorrend nem cserélhető fel: az extrákat ELŐBB beolvassuk (kellenek az
    ID-ik ahhoz, hogy a TIG-eken felismerjük, melyik relation mutat rájuk),
    a TIG-ek feldolgozása közben gyűjtjük össze, melyik extra kihez és melyik
    hónaphoz tartozik, és csak utána visszük fel őket - végül a maradékból
    jön az alapbér."""
    result = ImportResult(entity_type="BelsosTig")
    extra_oldalak = [
        (page, extract_properties(page, client))
        for page in client.query_database(db_ids.BELSOS_EXTRA_KIADASOK)
    ]
    extra_idk = {page["id"] for page, _ in extra_oldalak}
    hozzarendeles: dict[str, tuple[int, int, int]] = {}

    _import_tigek(client, db, result, extra_idk, hozzarendeles)
    _import_extrak(db, result, extra_oldalak, hozzarendeles)
    _alapber_potlas(db, result)
    return result
