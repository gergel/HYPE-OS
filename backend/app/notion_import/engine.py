"""Generikus, idempotens import-motor: minden importer ezt használja a Notion page ->
HYPE OS rekord létrehozásához/frissítéséhez, és a Notion relation mezők (page ID lista)
a mi FK-jainkra való feloldásához a NotionImportMap táblán keresztül.

Öt éves, élesben használt Notion adat garantáltan tartalmaz olyan sorokat, amik
megsértik a mi szigorúbb sémánk valamelyik megszorítását (pl. két employee ugyanazzal
az e-mail-lel). Ezért minden egyes rekord upsertje saját SAVEPOINT-ban fut: ha egy sor
hibás, csak az a sor esik ki (a result.errors-ba kerül a konkrét okkal), a többi attól
még bekerül."""

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
    # A Notionból átemelt fájlok száma és a kimaradt fájlok okai. Külön a
    # sor-hibáktól: egy le nem tölthető csatolmány nem hibás rekord, a sor
    # attól még rendben bekerült - csak a fájlja nem jött vele.
    files_copied: int = 0
    file_errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        summary = f"{self.entity_type}: {self.created} új, {self.updated} frissítve, {self.skipped} kihagyva"
        if self.files_copied:
            summary += f", {self.files_copied} fájl átemelve"
        if self.errors:
            summary += f", {len(self.errors)} hiba"
        if self.file_errors:
            summary += f", {len(self.file_errors)} fájl kimaradt"
        return summary

    def error_report(self) -> str:
        lines = [f"  [{self.entity_type}] {msg}" for msg in self.errors]
        lines += [f"  [{self.entity_type}] {msg}" for msg in self.file_errors]
        return "\n".join(lines)


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


def _eltavolitott_mezok_nelkul(db: Session, model: type, fields: dict[str, Any]) -> dict[str, Any]:
    """Kihagyja azokat a mezőket, amiket admin eltávolított a rendszerből (lásd
    services/entity_fields.py). Enélkül egy újabb Notion-import visszatöltené
    pont azt az adatot, amit a felhasználó szándékosan kitörölt - az importált
    mezőkészletből ugyanis sok itt már nem kell."""
    from app.services.entity_fields import hidden_fields
    from app.services.entity_registry import ENTITY_MODELS

    # A modellből visszakeressük az entitás kulcsát: az importerek saját,
    # nagybetűs neveket használnak ("Employee"), a mezőkezelés viszont az API
    # kulcsait ("employee") - a modell a közös, biztos kapocs.
    entity_key = next((key for key, m in ENTITY_MODELS.items() if m is model), None)
    if entity_key is None:
        return fields
    eltavolitott = hidden_fields(db, entity_key)
    if not eltavolitott:
        return fields
    return {k: v for k, v in fields.items() if k not in eltavolitott}


def upsert(db: Session, model: type, entity_type: str, notion_page_id: str, fields: dict[str, Any]) -> tuple[Any, bool]:
    """Létrehoz vagy frissít egy rekordot a notion_page_id alapján - ez teszi idempotenssé
    az importot (újrafuttatásnál nem duplikál). (rekord, is_new) párt ad vissza.

    Nincs benne hibakezelés - importeren belül a safe_upsert()-öt használd, hacsak nem
    vagy biztos benne, hogy a hívó már véd egy savepoint-tal (lásd get_or_create_unknown_client)."""
    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == notion_page_id))
    fields = _eltavolitott_mezok_nelkul(db, model, fields)

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


def safe_upsert(
    db: Session,
    result: ImportResult,
    model: type,
    entity_type: str,
    notion_page_id: str,
    fields: dict[str, Any],
    label: str,
) -> Any | None:
    """upsert() SAVEPOINT-tal védve: ha ez az egy sor hibázik (pl. UNIQUE ütközés egy
    duplikált e-mailen/sorozatszámon), csak ez a sor esik ki - a result.errors-ba kerül
    a konkrét hibaüzenet és a `label` (hogy a Notion-ban vissza lehessen keresni), a
    tranzakció a savepointig visszagörgetve folytatódik. None-t ad vissza hiba esetén,
    az importer ilyenkor `continue`-zzon a ciklusban."""
    try:
        with db.begin_nested():
            obj, created = upsert(db, model, entity_type, notion_page_id, fields)
        if created:
            result.created += 1
        else:
            result.updated += 1
        return obj
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció, szándékosan széles
        result.errors.append(f"{label} (notion_page_id={notion_page_id}): {type(exc).__name__}: {exc}")
        return None


def run_importer(name: str, db: Session, fn, *args, **kwargs) -> ImportResult:
    """Egy importer futtatása izolálva, saját tranzakcióval - ha maga az importer
    (nem egy adott sor, hanem a séma feldolgozó kód) hibára fut, rollback-elünk és a
    többi importer attól még lefut a következő (tiszta) tranzakcióban."""
    try:
        result = fn(*args, **kwargs)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001 - szándékosan széles, hogy egy hibás importer ne állítsa meg a többit
        db.rollback()
        result = ImportResult(entity_type=name)
        result.errors.append(f"importer szintű hiba: {type(exc).__name__}: {exc}")
        return result
