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
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
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
from app.services.hu_datum import elozo_honap, ev_honap_szoveg
from app.services.portal_storage import R2NotConfiguredError

# A Notion-tábla neve. Kisbetűsítve, ékezet nélkül hasonlítunk, hogy a
# "Belsős TIG-ek" / "Belsos TIG" írásmód is találjon.
BELSOS_TIG_TABLA_NEVEK = ("belsos tig", "belsos tigek", "belsos havi tig", "belsos tig-ek")

# Mezőnév-jelöltek. Az ELSŐ nem üres érték nyer (lásd _mezo).
NEV_SZEMELY = ("Belsős", "Belsos", "Személy", "Munkatárs", "Külsős és belsős", "👥 Külsős és belsős", "Név")
NEV_TIG_FAJL = ("TIG aláírva", "TIG aláírás", "Aláírt TIG", "TIG", "TIG link")
NEV_SZAMLA = ("Számla", "Kiállított számla", "Számla pdf", "Számla fájl")
NEV_NETTO = ("Nettó", "Nettó összeg", "Netto")
NEV_BRUTTO = ("Bruttó", "Bruttó összeg", "Brutto")
NEV_FIZ_HATARIDO = ("Fizetési határidő", "Fizetesi hatarido", "Fizetési határidő dátuma")
NEV_UTALAS = ("Utalás dátuma", "Utalas datuma", "Utalás", "Kifizetés dátuma")
NEV_TELJESITES = ("Teljesítés dátuma", "Teljesítés", "Teljesites datuma", "Teljesítés ideje")
NEV_KELTEZES = ("Keltezés", "Keltezés dátuma", "Kelt", "Keltezes")
NEV_ALLAPOT = ("Állapot", "Státusz", "Status", "Statusz")
NEV_MEGJEGYZES = ("Megjegyzés", "Megjegyzes", "Comment")
NEV_HONAP = ("Hónap", "Melyik hónap", "Elszámolás hónapja", "Honap")

# A "Belsős extra kiadások" tábla mezői (ezeket a discovery már kiírta, lásd
# importers_wave2.import_expenses - ugyanezt a táblát Expense-ként is bevisszük).
NEV_EXTRA_MEGNEVEZES = ("Megnevezés", "Név")
NEV_EXTRA_OSSZEG = ("Összeg", "Bruttó", "Nettó")
NEV_EXTRA_DATUM = ("Kiadás időpontja", "Dátum", "Kiadás dátuma")
NEV_EXTRA_TIG = ("Belsős TIG", "Belsős Havi TIG", "TIG")
NEV_EXTRA_SZEMELY = ("Személy", "Belsős", "Munkatárs")
NEV_EXTRA_PROJEKTKOD = ("Projektkód", "HYPE ADMIN projektkódok", "Projekt")

MAX_MEGNEVEZES = 255


def _ekezet_nelkul(szoveg: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFKD", szoveg.lower()) if not unicodedata.combining(c)
    ).strip()


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


def _fajl_urlek(ertek: Any) -> list[str]:
    if ertek is None:
        return []
    if isinstance(ertek, str):
        return [ertek]
    if isinstance(ertek, list):
        return [u for u in ertek if isinstance(u, str) and u]
    return []


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


def _employee_id(db: Session, props: dict, page_cim: str | None) -> int | None:
    """A TIG munkatársa. Elsődlegesen relation-ből (ez biztos kapcsolat), és
    csak ha az nincs, akkor a sor CÍMÉBŐL név szerint - utóbbi csak akkor, ha
    pontosan egy munkatársra illik, hogy egy névrokon miatt ne kerüljön valaki
    más TIG-je egy másik emberhez."""
    for nev in NEV_SZEMELY:
        ertek = props.get(nev)
        if isinstance(ertek, list) and ertek:
            talalat = resolve_relation_id(db, "Employee", ertek)
            if talalat is not None:
                return talalat
    if not page_cim:
        return None
    # A cím gyakran "Kovács Béla - 2026. május" alakú: az első kötőjelig vesszük.
    nev_resz = page_cim.split(" - ")[0].split(" – ")[0].strip()
    if len(nev_resz) < 4:
        return None
    talalatok = db.scalars(select(Employee).where(Employee.full_name.ilike(nev_resz))).all()
    return talalatok[0].id if len(talalatok) == 1 else None


def _honap(props: dict, teljesites: date | None, keltezes: date | None) -> tuple[int, int] | None:
    """Melyik hónap TIG-je ez.

    A rendszer szabálya: a hónapot a TELJESÍTÉS dátuma adja, és mindig az azt
    MEGELŐZŐ hónapot jelenti (2026.06.20-i teljesítés = a 2026. MÁJUSI TIG) -
    lásd services/hu_datum.elozo_honap. Ha van explicit hónap-mező, az erősebb:
    az a szándékot mondja ki, nem következtetni kell rá."""
    explicit = as_date(_mezo(props, NEV_HONAP))
    if explicit is not None:
        return explicit.year, explicit.month
    if teljesites is not None:
        return elozo_honap(teljesites)
    if keltezes is not None:
        return elozo_honap(keltezes)
    return None


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

    Idempotens a notion_forras-on keresztül: egy újrafuttatás nem tölti le és
    nem duplikálja ugyanazt a számlát."""
    for url in _fajl_urlek(_mezo(props, NEV_SZAMLA)):
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


def _import_tigek(client: NotionClient, db: Session, result: ImportResult) -> None:
    database_id = belsos_tig_database_id(client)
    if database_id is None:
        result.errors.append(
            "A 'Belsős TIG' Notion tábla nem található. Oszd meg az integrációval "
            "(Notion: '...' -> Connections), vagy vedd fel az ID-ját a "
            "notion_import/database_ids.py BELSOS_TIG konstansába."
        )
        return

    for page in client.query_database(database_id):
        props = extract_properties(page, client)
        cim = _page_cim(page, props)
        employee_id = _employee_id(db, props, cim)
        if employee_id is None:
            result.skipped += 1
            result.errors.append(f"Belsős TIG '{cim or page['id']}': nem azonosítható a munkatárs, kihagyva")
            continue

        teljesites = as_date(_mezo(props, NEV_TELJESITES))
        keltezes = as_date(_mezo(props, NEV_KELTEZES))
        honap_par = _honap(props, teljesites, keltezes)
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
        # Ha a Notionban a bruttó érdemben nagyobb a nettónál, az ÁFA-s eset.
        plusz_afa = bool(netto and brutto and brutto > netto * 1.05)
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
                # Régi, lezárt hónapok: ha a Notionban nincs állapot, a
                # meglévő TIG-dokumentum/összeg alapján "Kész" - így nem
                # kerülnek vissza a "készítendő" listára évekkel később.
                "allapot": _text(_mezo(props, NEV_ALLAPOT)) or ("Kész" if (netto or teljesites) else None),
                "megjegyzes": (_text(_mezo(props, NEV_MEGJEGYZES)) or None),
                "netto_osszeg": netto if netto is not None else brutto,
                "plusz_afa": plusz_afa,
                "teljesites_datuma": teljesites,
                "keltezes": keltezes,
                "fizetesi_hatarido": as_date(_mezo(props, NEV_FIZ_HATARIDO)),
                "utalas_datuma": utalas,
                # Az utalás dátuma maga a kifizetés ténye. Expense sort
                # SZÁNDÉKOSAN nem hozunk létre hozzá (ellentétben a felületi
                # "kifizetve" gombbal): a régi kifizetések a Notion 'Kiadások'
                # tábláján keresztül már bejönnek, egy második sor duplán
                # terhelné a pénzügyi kimutatásokat.
                "szamla_kifizetve": utalas is not None,
            },
            label=f"Belsős TIG '{cim or ''}' ({ev_honap_szoveg(ev, honap)})",
        )
        if tig is None:
            continue
        _tig_dokumentum(db, props, tig, result)
        _tig_szamlai(db, props, tig, result)


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


def _import_extrak(client: NotionClient, db: Session, result: ImportResult) -> None:
    """A 'Belsős extra kiadások' tábla havi tételként.

    Ugyanez a tábla Expense-ként IS bejön (importers_wave2.import_expenses) -
    ott a pénzügyi kimutatás miatt, itt azért, hogy a munkatárs havi
    elszámolásában lássuk, miből állt össze az összeg. A kettőt összekötjük
    (expense_id), hogy a felületen egyszer szerepeljen, ne kétszer."""
    for page in client.query_database(db_ids.BELSOS_EXTRA_KIADASOK):
        props = extract_properties(page, client)
        megnevezes = _text(_mezo(props, NEV_EXTRA_MEGNEVEZES))
        osszeg = _szam(_mezo(props, NEV_EXTRA_OSSZEG))
        if not megnevezes or osszeg is None or osszeg == 0:
            result.skipped += 1
            continue

        employee_id = None
        for nev in NEV_EXTRA_SZEMELY:
            ertek = props.get(nev)
            if isinstance(ertek, list) and ertek:
                employee_id = resolve_relation_id(db, "Employee", ertek)
                if employee_id is not None:
                    break
        if employee_id is None:
            result.skipped += 1
            continue

        datum = as_date(_mezo(props, NEV_EXTRA_DATUM))
        honap_par = _tetel_honapja(db, props, datum)
        if honap_par is None:
            result.skipped += 1
            result.errors.append(f"Belsős extra '{megnevezes}': nincs dátuma és TIG-je sem, kihagyva")
            continue
        ev, honap = honap_par

        # A negatív összeg levonás. Nálunk a levonandó tétel összege POZITÍV,
        # az előjelet a típus adja (lásd models/employee_monthly_item.py).
        tipus = "levonando" if osszeg < 0 else "extra"

        project_code_id = None
        for nev in NEV_EXTRA_PROJEKTKOD:
            ertek = props.get(nev)
            if isinstance(ertek, list) and ertek:
                project_code_id = resolve_relation_id(db, "ProjectCode", ertek)
                if project_code_id is not None:
                    break

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
    """Belsős TIG + a hozzá tartozó havi extrák + alapbér-maradék."""
    result = ImportResult(entity_type="BelsosTig")
    _import_tigek(client, db, result)
    _import_extrak(client, db, result)
    _alapber_potlas(db, result)
    return result
