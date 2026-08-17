"""A projektkódok PROJEKT NEVE a Notionból - és semmi más.

A Notion "HYPE ADMIN projektkódok" táblájában minden soron ki van töltve a
*PROJECT NÉV*, nálunk viszont sok projektkódnál üres maradt. Az okot a
notion_import/engine.py `_orokbefogadas` javítása szüntette meg (a meglévő
rekordot az import újra létrehozni próbálta, és egyedi mezőn ez ütközéssel
kiesett) - de a teljes projektkód-import 780 lapot és a hozzájuk tartozó
csatolmányokat is végigjárja, ami hosszú.

Ez a lépés csak a NEVEKÉRT megy el: egyetlen lekérdezés-sorozat, fájlok
nélkül, és pontosan egy mezőt tölt ki. Így percek helyett másodpercek alatt a
helyére kerül az, ami eddig hiányzott.

Amit már beírtak ide, azt nem írja felül: a kézzel adott név erősebb, mint a
Notionban álló. A napló külön kiírja, hányat töltött ki, hányat hagyott
érintetlenül, és melyik kódot nem találta meg."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_code import ProjectCode
from app.notion_import import database_ids as db_ids
from app.notion_import.client import NotionClient, extract_properties
from app.notion_import.engine import ImportResult
from app.notion_import.importers import _text
from app.services.projektkod_kotes import kulcs


def import_projektkod_nevek(client: NotionClient, db: Session) -> ImportResult:
    """ProjectCode.project_nev <- 'HYPE ADMIN projektkódok' / PROJECT NÉV."""
    result = ImportResult(entity_type="Projektkód nevek")

    # A kódokat kis/nagybetűtől és szóköztől függetlenül párosítjuk (ugyanaz a
    # szabály, mint a projektkód-kötésnél): a Notionban ugyanaz a kód másképp
    # írva is előfordul, és emiatt nem maradhat el a név.
    index: dict[str, ProjectCode] = {}
    for pc in db.scalars(select(ProjectCode).order_by(ProjectCode.id)):
        index.setdefault(kulcs(pc.projektkod), pc)

    for page in client.query_database(db_ids.HYPE_ADMIN_PROJEKTKODOK):
        props = extract_properties(page, client)
        kod = _text(props.get("PROJEKTKÓD"))
        nev = _text(props.get("PROJECT NÉV"))
        if not kod or not nev:
            result.skipped += 1
            continue

        pc = index.get(kulcs(kod))
        if pc is None:
            result.skipped += 1
            result.errors.append(
                f"Projektkód nevek: a(z) '{kod}' kód nincs meg a rendszerben - "
                "előbb a Projektkódok importja kell."
            )
            continue

        if (pc.project_nev or "").strip():
            # Már van neve: ha ugyanaz, nincs teendő; ha más, azt itt írták be.
            if (pc.project_nev or "").strip() != nev:
                result.protected_fields += 1
                result.protected_rows += 1
            continue

        pc.project_nev = nev
        result.updated += 1

    db.flush()
    return result
