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
KATEGORIAK = ("szerzodes", "tig", "szamla", "diszpo", "egyeb")

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
    "project": "/projektek",
    "client": "/ugyfelek",
    "employee": "/csapat",
    "deliverable": "/utomunka",
    "task": "/feladatok",
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
}

MAX_MERET_BAJT = 100 * 1024 * 1024


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


def list_by_kategoria(db: Session, entity_type: str, entity_id: int, kategoria: str) -> list[DocumentAttachment]:
    return [a for a in list_for(db, entity_type, entity_id) if a.kategoria == kategoria]


def by_notion_source(db: Session, notion_forras: str) -> DocumentAttachment | None:
    return db.scalar(
        select(DocumentAttachment).where(DocumentAttachment.notion_forras == notion_forras).limit(1)
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
