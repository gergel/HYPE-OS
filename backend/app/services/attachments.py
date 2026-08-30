"""Rekordokhoz csatolt fájlok (szerződés / TIG / számla / egyéb) kezelése.

Egyetlen szabály van, és ez a modul kényszeríti ki: a feltöltött fájl TARTALMA
mindig az R2 tárhelyre kerül (lásd document_storage.py), az adatbázisba csak a
hivatkozás (kulcs + publikus URL + fájlnév). A szolgáltatás saját lemezére
soha semmit nem írunk: a Railway konténer fájlrendszere minden deploynál és
újraindításnál tiszta lappal indul, egy oda mentett szerződés vagy számla
nyomtalanul eltűnne.
"""

from __future__ import annotations

import os
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment
from app.services import document_storage

# A fájl szerepe. A "diszpo" külön kategória, mert ezek a fájlok NEM csak
# tárolódnak: a diszpó kiküldésekor a levél mellékleteként ki is mennek a
# stábnak (lásd services/dispo.py). Ezért nem lehet közös az "egyeb"-bel -
# különben minden, a projekthez feltöltött fájl kiszaladna a stábnak.
# Az "egyeb" a gyűjtő: ami nem szerződés/TIG/számla/diszpó-melléklet, csak a
# pénzügyi gyűjtésekbe (havi számla-ZIP) nem számít bele.
#: A "gyartas" a projekt Gyártás komment dobozához tartozó fájloké: a
#: gyártásvezetői jegyzet mellé feltöltött forgatókönyv, helyszínrajz, brief.
#: Külön kategória, hogy a doboz csak a sajátjait mutassa, és ne keveredjen a
#: diszpó mellékleteivel.
KATEGORIAK = ("szerzodes", "tig", "szamla", "diszpo", "gyartas", "egyeb")

# Melyik entitáshoz melyik oldal jogosultsága kell a fel-/letöltéshez. Ami
# nincs a listán, ahhoz nem lehet fájlt csatolni - így egy elgépelt vagy
# kitalált entity_type nem nyit meg egy ellenőrizetlen feltöltési utat.
ENTITAS_OLDALAK: dict[str, str] = {
    # A szerződések jogosultsága a Pénzügyek oldalé (a Keretszerződések menüpont
    # is erre hivatkozik, lásd frontend lib/nav.ts permissionPage).
    "contract": "/penzugyek",
    "projectCode": "/projektek/project-kodok",
    "expense": "/penzugyek",
    "revenue": "/penzugyek",
    "kpForgalom": "/penzugyek",
    "project": "/projektek",
    "client": "/ugyfelek",
    "employee": "/csapat",
    "deliverable": "/utomunka",
    # Egy hozzászólás az Utómunka oldal alján - lásd entity_registry.py.
    "deliverableComment": "/utomunka",
    "task": "/feladatok",
    "hypeTodo": "/hype-todo-lista",
    "floraFeladat": "/flora",
    "agiTodo": "/agi",
    # Egy kötelezettség adott fordulójához (hónap/év) tartozó számla - az
    # E-Rezsi, a Biztosítások és az autók lapja is ide tölt (lásd
    # routes/kotelezettsegek.py CSATOLMANY_ENTITAS).
    "kotelezettsegIdoszak": "/kotelezettsegek",
    # Magához a kötelezettséghez tartozó papír: kötvény, szerződés, a forgalmi
    # másolata - nem egy fizetéshez, hanem az egészhez tartozik.
    "kotelezettseg": "/kotelezettsegek",
    # Egy autós költés bizonylata. Ugyanaz a tábla, mint az "expense", de az
    # AUTÓK oldalának jogosultságával - egy tankolási blokkhoz ne kelljen
    # hozzáférés a cég teljes pénzügyéhez (lásd routes/autok.py).
    "autoKiadas": "/autok",
    # A Krumpello kiadás-tétele és napi kassza-zárása. A számla feltöltése
    # SEHOL NEM KÖTELEZŐ: az "extra" tételnek épp az a lényege, hogy nincs
    # hozzá papír (lásd models/krumpello.py EXTRA_FORRAS) - a lehetőség attól
    # még kell, mert a többinél van blokk vagy számla, és eddig nem volt hova
    # tenni.
    "krumpelloKiadas": "/krumpello",
    "krumpelloNap": "/krumpello",
}

MAX_MERET_BAJT = 100 * 1024 * 1024

# A "diszpo" kategória KÜLÖN, szigorúbb határt kap, mert ezek a fájlok nem csak
# tárolódnak: a diszpó levél mellékleteként ki is mennek a stábnak. A Gmail
# üzenetkorlátja 25 MB, a base64 kódolás ~33%-kal növeli a méretet, és a levél
# többi része (HTML, diszpó PDF) is elfér benne - innen a 15 MB.
#
# A határt a FELTÖLTÉSNÉL kérjük számon, nem csak küldéskor: enélkül a fájl
# szépen felmegy, és csak napokkal később, a diszpó kiküldésekor derül ki, hogy
# nem megy ki - amikor már nincs idő Drive-ra tölteni és linket cserélni.
# A küldés oldali ellenőrzés ugyanezt a konstanst használja (services/dispo.py).
DISZPO_MAX_BAJT = 15 * 1024 * 1024

#: Amit ilyenkor mondunk: a nagy fájl helye a Drive, a linkjéé a brief - a
#: brief szövege a diszpó levélbe is bekerül, tehát a link így is eljut a stábhoz.
DISZPO_TULLEPES_TANACS = (
    "Töltsd fel a fájlt Google Drive-ra, és a megosztási linket tedd be a projekt "
    "briefjébe - a brief szövege a diszpóval együtt megy ki, így a stáb eléri."
)


class AttachmentError(Exception):
    """Feltöltési/tárolási hiba, amit a hívó HTTP-hibává fordít."""


def _tiszta_fajlnev(nev: str) -> str:
    """Ékezet- és szóköz-mentes, tárhely-barát fájlnév az R2 kulcshoz. A
    MEGJELENÍTETT név ettől független (az eredeti marad az adatbázisban) -
    ez csak azért kell, hogy az objektumkulcs URL-ben is jól viselkedjen."""
    alap = unicodedata.normalize("NFKD", nev).encode("ascii", "ignore").decode()
    alap = re.sub(r"[^A-Za-z0-9._-]+", "-", alap).strip("-")
    return alap or "fajl"


def list_for(db: Session, entity_type: str, entity_id: int) -> list[DocumentAttachment]:
    return list(
        db.scalars(
            select(DocumentAttachment)
            .where(DocumentAttachment.entity_type == entity_type, DocumentAttachment.entity_id == entity_id)
            .order_by(DocumentAttachment.id)
        ).all()
    )


def list_for_many(db: Session, entity_type: str, entity_ids: list[int]) -> dict[int, list[DocumentAttachment]]:
    """Ugyanaz, mint a `list_for`, csak EGY lekérdezéssel több rekordra egyszerre
    - listás nézeteknél kell (pl. egy hozzászólás-lista minden sora a saját
    csatolmányait mutatja), ahol a soronkénti `list_for` N+1 lekérdezést adna."""
    if not entity_ids:
        return {}
    eredmeny: dict[int, list[DocumentAttachment]] = {i: [] for i in entity_ids}
    for a in db.scalars(
        select(DocumentAttachment)
        .where(DocumentAttachment.entity_type == entity_type, DocumentAttachment.entity_id.in_(entity_ids))
        .order_by(DocumentAttachment.id)
    ).all():
        eredmeny[a.entity_id].append(a)
    return eredmeny


def list_by_kategoria(db: Session, entity_type: str, entity_id: int, kategoria: str) -> list[DocumentAttachment]:
    return [a for a in list_for(db, entity_type, entity_id) if a.kategoria == kategoria]


def by_notion_source(db: Session, notion_forras: str) -> DocumentAttachment | None:
    return db.scalar(
        select(DocumentAttachment).where(DocumentAttachment.notion_forras == notion_forras).limit(1)
    )


def _meret(bajt: int) -> str:
    """Olvasható méret - 1 MB alatt kB-ban, hogy egy pár kilobájtos fájl ne
    "0.0 MB"-ként jelenjen meg a hibaüzenetben."""
    if bajt < 1024 * 1024:
        return f"{round(bajt / 1024)} kB"
    return f"{bajt / 1024 / 1024:.1f} MB"


def _ellenorizd_a_diszpo_meretet(db: Session, entity_type: str, entity_id: int, uj_meret: int) -> None:
    """A diszpó-mellékletek EGYÜTT sem lehetnek nagyobbak a levélbe csatolható
    méretnél - a most feltöltött fájllal együtt számolva.

    Azért az együttes méret számít, nem csak az új fájlé: a levélbe mindegyik
    bekerül, tehát három 6 MB-os fájl ugyanúgy megbuktatja a küldést, mint egy
    18 MB-os."""
    mar_fent = sum(a.meret_bajt or 0 for a in list_by_kategoria(db, entity_type, entity_id, "diszpo"))
    if mar_fent + uj_meret <= DISZPO_MAX_BAJT:
        return
    if mar_fent:
        raise AttachmentError(
            f"Ez a fájl ({_meret(uj_meret)}) már nem fér a diszpó levélbe: a csatolni valók együtt "
            f"{_meret(mar_fent + uj_meret)} lennének, a határ {_meret(DISZPO_MAX_BAJT)}. " + DISZPO_TULLEPES_TANACS
        )
    raise AttachmentError(
        f"A fájl túl nagy ({_meret(uj_meret)}) ahhoz, hogy a diszpó levélhez csatolható legyen "
        f"(a határ {_meret(DISZPO_MAX_BAJT)}). " + DISZPO_TULLEPES_TANACS
    )


def save(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    kategoria: str,
    filename: str,
    data: bytes,
    content_type: str | None = None,
    notion_forras: str | None = None,
) -> DocumentAttachment:
    """A fájlt feltölti az R2-re, és felveszi a hivatkozást az adatbázisba.

    A sort ELŐBB hozzuk létre (flush), hogy az id-ból képezhessünk ütközésmentes
    tárhely-kulcsot: két azonos nevű számla ugyanahhoz a projektkódhoz így sem
    írja felül egymást."""
    if kategoria not in KATEGORIAK:
        raise AttachmentError(f"Ismeretlen kategória: {kategoria}")
    if len(data) > MAX_MERET_BAJT:
        raise AttachmentError(
            f"A fájl túl nagy ({len(data) / 1024 / 1024:.1f} MB), a felső határ {MAX_MERET_BAJT // 1024 // 1024} MB."
        )
    if not data:
        raise AttachmentError("A fájl üres.")
    if kategoria == "diszpo":
        _ellenorizd_a_diszpo_meretet(db, entity_type, entity_id, len(data))

    filename = filename or "dokumentum"
    rekord = DocumentAttachment(
        entity_type=entity_type,
        entity_id=entity_id,
        kategoria=kategoria,
        filename=filename,
        storage_key="",
        url="",
        content_type=content_type,
        meret_bajt=len(data),
        notion_forras=notion_forras,
    )
    db.add(rekord)
    db.flush()

    kiterjesztes = os.path.splitext(filename)[1][:12]
    kulcs = f"csatolmany/{entity_type}/{entity_id}/{rekord.id}-{_tiszta_fajlnev(os.path.splitext(filename)[0])}{kiterjesztes}"
    rekord.url = document_storage.upload_bytes(data, kulcs, content_type or "application/octet-stream")
    rekord.storage_key = kulcs
    db.flush()
    return rekord


def delete(db: Session, rekord: DocumentAttachment) -> None:
    """A hivatkozást törli, és az R2 objektumot is - de CSAK akkor, ha nincs
    másik csatolmány ugyanarra a kulcsra. A Notion importban ugyanaz a feltöltött
    fájl több rekordhoz is tartozhat (ugyanaz a szerződés a projektkódon és a
    keretszerződésen is); ilyenkor az egyik törlése nem üresítheti ki a másikat."""
    masik = db.scalar(
        select(DocumentAttachment.id)
        .where(DocumentAttachment.storage_key == rekord.storage_key, DocumentAttachment.id != rekord.id)
        .limit(1)
    )
    db.delete(rekord)
    db.flush()
    if masik is None and rekord.storage_key:
        document_storage.delete_object(rekord.storage_key)
