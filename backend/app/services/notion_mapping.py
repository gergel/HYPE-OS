"""A Notion-leképezések takarítása rekord törlésekor.

A `notion_import_map` GENERIKUS tábla: (Notion oldal -> entitástípus + id)
párokat tart, idegen kulcs nélkül - így nincs az adatbázisban semmi, ami a
rekord törlésekor magától elvinné a hozzá tartozó sort.

Miért baj ez? Mert az árván maradt leképezés VÉGLEG kizárja azt a Notion-oldalt
az importból: az import a leképezésből azt hiszi, hogy a rekord már megvan,
ezért frissíteni próbálná - de nincs mit. (A motor ma már fel is ismeri és
újrahasznosítja az árva leképezést, lásd notion_import/engine.upsert; ez a
takarítás azt előzi meg, hogy egyáltalán árva legyen.)
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.notion_import import NotionImportMap


def torold_a_leképezest(db: Session, entity_type: str, entity_id: int) -> None:
    """Egy törölt rekord Notion-leképezésének eltakarítása.

    Az `entity_type` az IMPORTER neve ("Contract", "Employee", ...), nem az
    API entitáskulcsa - a leképezést az import írja, azzal a névvel."""
    db.execute(
        delete(NotionImportMap).where(
            NotionImportMap.entity_type == entity_type, NotionImportMap.entity_id == entity_id
        )
    )
