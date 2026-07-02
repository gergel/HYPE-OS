"""Generikus, idempotens import-motor: minden importer ezt használja a Notion page ->
HYPE OS rekord létrehozásához/frissítéséhez, és a Notion relation mezők (page ID lista)
a mi FK-jainkra való feloldásához a NotionImportMap táblán keresztül."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notion_import import NotionImportMap


@dataclass
class ImportResult:
    entity_type: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        summary = f"{self.entity_type}: {self.created} új, {self.updated} frissítve, {self.skipped} kihagyva"
        if self.errors:
            summary += f", {len(self.errors)} hiba"
        return summary


def resolve_relation_ids(db: Session, entity_type: str, notion_page_ids: list[str]) -> list[int]:
    """Notion relation (page ID lista) -> a mi entitásaink integer ID-i. Azokat a
    kapcsolatokat, amiknek a célja még nincs importálva, csendben kihagyja."""
    if not notion_page_ids:
        return []
    rows = db.scalars(
        select(NotionImportMap).where(
            NotionImportMap.entity_type == entity_type,
            NotionImportMap.notion_page_id.in_(notion_page_ids),
        )
    ).all()
    return [r.entity_id for r in rows]


def resolve_relation_id(db: Session, entity_type: str, notion_page_ids: list[str]) -> int | None:
    ids = resolve_relation_ids(db, entity_type, notion_page_ids)
    return ids[0] if ids else None


def upsert(db: Session, model: type, entity_type: str, notion_page_id: str, fields: dict[str, Any]) -> tuple[Any, bool]:
    """Létrehoz vagy frissít egy rekordot a notion_page_id alapján - ez teszi idempotenssé
    az importot (újrafuttatásnál nem duplikál). (rekord, is_new) párt ad vissza."""
    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == notion_page_id))

    if mapping:
        obj = db.get(model, mapping.entity_id)
        for key, value in fields.items():
            setattr(obj, key, value)
        db.flush()
        return obj, False

    obj = model(**fields)
    db.add(obj)
    db.flush()  # kell az obj.id-hoz, mielőtt a mapping sort felvesszük
    db.add(NotionImportMap(notion_page_id=notion_page_id, entity_type=entity_type, entity_id=obj.id))
    db.flush()
    return obj, True


def run_importer(name: str, db: Session, fn, *args, **kwargs) -> ImportResult:
    """Egy importer futtatása izolálva, saját tranzakcióval - ha az egyik tábla
    feldolgozása hibára fut (pl. váratlan Notion mezőalak), rollback-elünk és a többi
    importer attól még lefut a következő (tiszta) tranzakcióban."""
    try:
        result = fn(*args, **kwargs)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001 - szándékosan széles, hogy egy hibás importer ne állítsa meg a többit
        db.rollback()
        result = ImportResult(entity_type=name)
        result.errors.append(f"{type(exc).__name__}: {exc}")
        return result
