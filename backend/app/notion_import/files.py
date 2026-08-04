"""A Notionba feltöltött fájlok átemelése a saját R2 tárhelyünkre.

Miért kell ez egyáltalán: a Notion "files" property-jei nem stabil linkek. A
Notionban TÁROLT fájlokra az API egy aláírt, kb. egy óra múlva LEJÁRÓ S3 URL-t
ad vissza. Ha ezt az URL-t egyszerűen beírnánk egy oszlopba (ahogy az import
korábban tette), másnap már minden szerződés-, TIG- és számla-link halott
volna. Ezért importáláskor le is TÖLTJÜK a fájlt, feltesszük az R2-re, és a
rekordhoz csatoljuk (lásd services/attachments.py).

A Notionban csak HIVATKOZOTT (external) fájlok - jellemzően Google Docs/Drive
linkek - nem járnak lejárattal és nem is a mieink: azokat érintetlenül
hagyjuk, marad a link.

Az egész lépés hibatűrő: ha egy fájl nem tölthető le (törölték, időtúllépés,
lejárt aláírás), az adott fájl kimarad egy naplósorral, az importált REKORD
attól még bekerül. Enélkül egyetlen döglött Notion-csatolmány elvihetné egy
egész tábla importját."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy.orm import Session

from app.services import attachments, document_storage
from app.services.portal_storage import R2NotConfiguredError

# A Notion saját tárhelyének hosztjai. Csak az innen jövő URL-ek járnak
# lejárattal - ezeket kell átmentenünk.
NOTION_FILE_HOSTS = (
    "prod-files-secure.s3.us-west-2.amazonaws.com",
    "prod-files-secure.s3.amazonaws.com",
    "s3.us-west-2.amazonaws.com",
    "s3-us-west-2.amazonaws.com",
    "file.notion.so",
    "files.notion.so",
)

LETOLTES_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
MAX_MERET_BAJT = attachments.MAX_MERET_BAJT

# Kikapcsolható: NOTION_IMPORT_FILES=0 mellett az import a régi módon fut
# (csak a linkeket írja be) - hasznos, ha egy gyors, csak-adat újrafuttatás kell.
def _bekapcsolva() -> bool:
    return os.environ.get("NOTION_IMPORT_FILES", "1").strip().lower() not in ("0", "false", "no")


def notion_fajl_e(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.hostname is None:
        return False
    if parsed.hostname not in NOTION_FILE_HOSTS:
        return False
    # Az s3.us-west-2.amazonaws.com alatt csak a Notion secure/static bucketje
    # a miénk - más bucketre mutató linket nem másolunk le.
    if parsed.hostname.startswith("s3") and "notion" not in parsed.path:
        return False
    return True


def forras_kulcs(url: str) -> str:
    """A Notion fájl VÁLTOZATLAN azonosítója: az URL útvonala aláírás nélkül.
    Az aláírt query-string minden lekérdezésnél más, az útvonal (workspace/
    block UUID + fájlnév) viszont ugyanaz - ezen múlik, hogy egy újrafuttatott
    import ne töltse le és ne duplikálja ugyanazt a fájlt."""
    parsed = urlparse(url)
    return f"{parsed.hostname}{parsed.path}"[:700]


def fajlnev(url: str) -> str:
    nyers = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    nyers = re.sub(r"[\r\n\t]", "", nyers).strip()
    return nyers[:255] or "notion-fajl"


def _letolt(url: str) -> tuple[bytes, str | None]:
    with httpx.Client(timeout=LETOLTES_TIMEOUT, follow_redirects=True) as client:
        with client.stream("GET", url) as valasz:
            valasz.raise_for_status()
            hossz = valasz.headers.get("Content-Length")
            if hossz and int(hossz) > MAX_MERET_BAJT:
                raise ValueError(f"túl nagy fájl ({int(hossz) / 1024 / 1024:.0f} MB)")
            darabok: list[bytes] = []
            meret = 0
            for darab in valasz.iter_bytes():
                meret += len(darab)
                if meret > MAX_MERET_BAJT:
                    raise ValueError("túl nagy fájl (letöltés közben lépte túl a határt)")
                darabok.append(darab)
            return b"".join(darabok), valasz.headers.get("Content-Type")


def atemel(
    db: Session,
    url: str | None,
    *,
    entity_type: str,
    entity_id: int,
    kategoria: str = "egyeb",
    log: Callable[[str], None] | None = None,
) -> str | None:
    """Egy Notion fájl-URL-t átemel az R2-re és a rekordhoz csatolja. A saját
    (R2-es) URL-t adja vissza, amit a hívó beírhat a régi URL-oszlopba - így a
    meglévő felületek is működő linket látnak.

    Nem Notion-fájl (külső link) esetén az URL-t VÁLTOZATLANUL adja vissza:
    ott nincs mit átmenteni. Hibánál None jön vissza."""
    if not url or not isinstance(url, str):
        return None
    if not notion_fajl_e(url):
        return url
    if not _bekapcsolva():
        return url

    forras = forras_kulcs(url)
    meglevo = attachments.by_notion_source(db, forras)
    if meglevo is not None:
        # Már átemeltük egy korábbi futásban. Ha másik rekordhoz tartozik,
        # felvesszük ide is - de a fájlt nem töltjük le még egyszer.
        if meglevo.entity_type == entity_type and meglevo.entity_id == entity_id:
            return meglevo.url
        masolat = type(meglevo)(
            entity_type=entity_type,
            entity_id=entity_id,
            kategoria=kategoria,
            filename=meglevo.filename,
            storage_key=meglevo.storage_key,
            url=meglevo.url,
            content_type=meglevo.content_type,
            meret_bajt=meglevo.meret_bajt,
            notion_forras=forras,
        )
        db.add(masolat)
        db.flush()
        return meglevo.url

    if not document_storage.is_configured():
        if log:
            log(f"  [fájl] R2 nincs beállítva - a Notion fájl linkje marad: {fajlnev(url)}")
        return url

    try:
        adat, content_type = _letolt(url)
        # A mentés SAVEPOINT-ban: az attachments.save() előbb felveszi a sort
        # (az id-ból képez tárhely-kulcsot), és csak utána tölt fel. Ha a
        # feltöltés elhasal, e nélkül egy féllábú, üres kulcsú csatolmány-sor
        # maradna a tranzakcióban.
        with db.begin_nested():
            rekord = attachments.save(
                db,
                entity_type=entity_type,
                entity_id=entity_id,
                kategoria=kategoria,
                filename=fajlnev(url),
                data=adat,
                content_type=content_type,
                notion_forras=forras,
            )
    except (httpx.HTTPError, ValueError, R2NotConfiguredError, attachments.AttachmentError) as exc:
        if log:
            log(f"NEM sikerült átemelni ({fajlnev(url)}): {type(exc).__name__}: {exc}")
        return url
    return rekord.url


def atemel_tobb(
    db: Session,
    urls: list | None,
    *,
    entity_type: str,
    entity_id: int,
    kategoria: str = "egyeb",
    log: Callable[[str], None] | None = None,
) -> list[str] | None:
    """Egy "files" property teljes listájára. A visszaadott lista ugyanolyan
    hosszú és sorrendű, mint a bemenet - csak a Notionban tárolt fájlok URL-je
    cserélődik a sajátunkra."""
    if not urls or not isinstance(urls, list):
        return urls
    return [atemel(db, u, entity_type=entity_type, entity_id=entity_id, kategoria=kategoria, log=log) or u for u in urls]


def kategoria_mezonevbol(prop_nev: str) -> str:
    """A fájl szerepét a Notion mező NEVÉBŐL állapítjuk meg ("Szerződés aláírva",
    "TIG aláírva", "Számla pdf"…). Ez azért működik jól, mert a HYPE Notion
    tábláiban a fájl-mezők neve következetesen megmondja, mi van bennük - és
    így nem kell táblánként kézzel felsorolni mind a több tucat mezőt."""
    nev = prop_nev.lower()
    # A "Csatolni való" a diszpó-levél melléklete - ugyanaz, amit a felületen
    # is a Diszpó küldése alatt lehet feltölteni (lásd services/dispo.py), így
    # a Notionból áthozott régi mellékletek is a helyükre kerülnek.
    if "csatolni" in nev:
        return "diszpo"
    if "szerződés" in nev or "szerzodes" in nev or "keretszerz" in nev:
        return "szerzodes"
    if "tig" in nev or "teljesítési" in nev:
        return "tig"
    if "számla" in nev or "szamla" in nev:
        return "szamla"
    return "egyeb"


def atemel_mindent(
    db: Session,
    props: dict,
    *,
    entity_type: str,
    entity_id: int,
    result=None,
) -> dict[str, list[str]]:
    """Egy Notion oldal ÖSSZES feltöltött fájlját átemeli a rekordhoz.

    Végigmegy minden property-n, és amiben Notionban TÁROLT fájl URL-je van
    (akár egyedül, akár listában), azt letölti és az R2-re teszi. Azért
    property-név szerinti felsorolás helyett söpréssel, mert a HYPE Notion
    tábláiban tucatnyi fájl-mező van, táblánként másképp elnevezve - a
    felsorolásból óhatatlanul kimaradna néhány, és pont az a fájl veszne el.

    A visszaadott dict csak azokat a property-ket tartalmazza, ahol tényleg
    történt átemelés: {property név: [új URL-ek]} - ebből tudja a hívó
    felülírni a saját oszlopait (pl. Contract.szerzodes_file_url) a mostantól
    állandó, saját linkre. A `result` (ImportResult) az átemelt fájlok számát
    és a kimaradtak okait gyűjti, hogy az admin felületen látszódjanak."""
    if not _bekapcsolva() or entity_id is None:
        return {}
    log = result.file_errors.append if result is not None else None
    eredmeny: dict[str, list[str]] = {}
    for nev, ertek in props.items():
        jeloltek = [ertek] if isinstance(ertek, str) else ertek if isinstance(ertek, list) else []
        if not any(notion_fajl_e(u) for u in jeloltek):
            continue
        kategoria = kategoria_mezonevbol(nev)
        ujak: list[str] = []
        for url in jeloltek:
            if not notion_fajl_e(url):
                ujak.append(url)
                continue
            # Fájlonként külön savepoint: egy sikertelen átemelés (pl. UNIQUE
            # ütközés vagy tárhely-hiba) ne görgesse vissza a rekordot magát.
            try:
                with db.begin_nested():
                    uj = atemel(
                        db, url, entity_type=entity_type, entity_id=entity_id, kategoria=kategoria, log=log
                    )
            except Exception as exc:  # noqa: BLE001 - fájlonkénti izoláció, szándékosan széles
                if log:
                    log(f"'{nev}' fájl átemelése kimaradt: {type(exc).__name__}: {exc}")
                uj = url
            if uj and uj != url and result is not None:
                result.files_copied += 1
            ujak.append(uj or url)
        eredmeny[nev] = ujak
    return eredmeny


def elso(ujak: dict[str, list[str]], prop_nev: str) -> str | None:
    """Az átemelt URL-ek közül az elsőt adja vissza egy property-hez, vagy
    None-t, ha ehhez a mezőhöz nem került át fájl."""
    ertekek = ujak.get(prop_nev) or []
    return ertekek[0] if ertekek else None
