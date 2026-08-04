"""Mezők eltávolítása és saját mezők - a rendszer EGYETLEN helye, ahol eldől,
mely mezők tartoznak egy entitáshoz.

A crud_router minden entitásra ezt hívja (lista, egy rekord, PATCH), ezért egy
eltávolított mező mindenhonnan eltűnik, egy saját mező pedig mindenhol úgy
viselkedik, mint egy valódi oszlop - a részletnézeten szerkeszthető, a
mezőtípusok között szerepel, és a fülekhez is hozzárendelhető.

Lásd models/entity_field.py a "miért nem valódi DROP COLUMN" indoklásért.
"""

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.entity_field import CustomFieldDef, CustomFieldValue, EntityFieldConfig
from app.services.entity_registry import ENTITY_MODELS

#: Ezeket sosem lehet eltávolítani: a rendszer működéséhez kellenek.
PROTECTED_FIELDS = {"id", "created_at", "updated_at"}

CUSTOM_FIELD_TYPES = ("text", "number", "boolean", "date", "datetime", "select")


def _model_or_404(entity_type: str) -> type:
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ismeretlen entitástípus: {entity_type}")
    return model


def hidden_fields(db: Session, entity_type: str) -> set[str]:
    """Az entitástípuson eltávolított (rendszerszinten elrejtett) mezőnevek."""
    rows = db.scalars(
        select(EntityFieldConfig.field_name).where(
            EntityFieldConfig.entity_type == entity_type, EntityFieldConfig.hidden.is_(True)
        )
    ).all()
    return set(rows)


def custom_defs(db: Session, entity_type: str) -> list[CustomFieldDef]:
    return list(
        db.scalars(
            select(CustomFieldDef)
            .where(CustomFieldDef.entity_type == entity_type)
            .order_by(CustomFieldDef.sort_order, CustomFieldDef.id)
        ).all()
    )


def custom_keys(db: Session, entity_type: str) -> set[str]:
    return {d.field_key for d in custom_defs(db, entity_type)}


def values_for_record(db: Session, entity_type: str, record_id: int) -> dict[str, Any]:
    """Egy rekord saját mezőinek értékei. A definiált, de még ki nem töltött
    mezők is szerepelnek (None értékkel), különben a részletnézeten meg sem
    jelennének - egy új mező mindig üresen indul, nem hiányzóként."""
    defs = custom_defs(db, entity_type)
    if not defs:
        return {}
    stored = {
        row.field_key: row.value
        for row in db.scalars(
            select(CustomFieldValue).where(
                CustomFieldValue.entity_type == entity_type, CustomFieldValue.record_id == record_id
            )
        )
    }
    return {d.field_key: stored.get(d.field_key) for d in defs}


def set_values(db: Session, entity_type: str, record_id: int, values: dict[str, Any]) -> None:
    """Saját mezők értékének mentése (a crud_router PATCH-e hívja, amikor a
    payloadban saját mező kulcsa szerepel). Nem commitol - a hívó tranzakciója
    zárja le, hogy a valódi oszlopokkal együtt mentődjön."""
    if not values:
        return
    engedett = custom_keys(db, entity_type)
    for key, value in values.items():
        if key not in engedett:
            continue
        row = db.scalar(
            select(CustomFieldValue).where(
                CustomFieldValue.entity_type == entity_type,
                CustomFieldValue.record_id == record_id,
                CustomFieldValue.field_key == key,
            )
        )
        if row is None:
            db.add(CustomFieldValue(entity_type=entity_type, record_id=record_id, field_key=key, value=value))
        else:
            row.value = value


def delete_values_for_record(db: Session, entity_type: str, record_id: int) -> None:
    """A rekord törlésekor a saját mezőinek értékei is menjenek vele - nincs
    idegen kulcs, ami ezt magától elintézné (a tábla generikus, minden
    entitástípushoz ugyanaz)."""
    for row in db.scalars(
        select(CustomFieldValue).where(
            CustomFieldValue.entity_type == entity_type, CustomFieldValue.record_id == record_id
        )
    ):
        db.delete(row)


# --- Admin műveletek --------------------------------------------------------


def remove_field(db: Session, entity_type: str, field_name: str, *, wipe_data: bool, employee_id: int) -> None:
    """Egy valódi (modell-)mező eltávolítása a rendszerből. wipe_data esetén a
    tárolt értékeket is kiüríti - ez visszavonhatatlan."""
    model = _model_or_404(entity_type)
    columns = model.__table__.columns
    if field_name not in columns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nincs ilyen mező: {field_name}")
    if field_name in PROTECTED_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A(z) '{field_name}' mező a rendszer működéséhez kell, nem távolítható el.",
        )
    column = columns[field_name]
    if column.primary_key or not column.nullable:
        # Egy kötelező oszlop eltávolítása után új rekordot sem lehetne
        # létrehozni (a mező eltűnne az űrlapról, de az adatbázis megkövetelné).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A(z) '{field_name}' kötelező mező, ezért nem távolítható el.",
        )

    if wipe_data:
        # Paraméterezni nem lehet oszlopnevet, ezért a fenti ellenőrzés a
        # védelem: a név csak a modell tényleges oszlopai közül jöhet.
        db.execute(text(f'UPDATE {model.__table__.name} SET "{field_name}" = NULL'))

    config = db.scalar(
        select(EntityFieldConfig).where(
            EntityFieldConfig.entity_type == entity_type, EntityFieldConfig.field_name == field_name
        )
    )
    if config is None:
        config = EntityFieldConfig(entity_type=entity_type, field_name=field_name)
        db.add(config)
    config.hidden = True
    config.data_wiped = bool(wipe_data) or bool(config.data_wiped)
    config.removed_by_employee_id = employee_id
    config.removed_at = datetime.now()
    db.commit()


def restore_field(db: Session, entity_type: str, field_name: str) -> None:
    """Visszahoz egy korábban eltávolított mezőt. Ha az eltávolításkor az
    adatait is kiürítettük, a mező üresen tér vissza."""
    config = db.scalar(
        select(EntityFieldConfig).where(
            EntityFieldConfig.entity_type == entity_type, EntityFieldConfig.field_name == field_name
        )
    )
    if config is None:
        return
    db.delete(config)
    db.commit()


def create_custom_field(
    db: Session,
    entity_type: str,
    *,
    field_key: str,
    label: str,
    field_type: str,
    options: list[str] | None,
    employee_id: int,
) -> CustomFieldDef:
    model = _model_or_404(entity_type)
    kulcs = field_key.strip()
    if not kulcs or not kulcs.replace("_", "").isalnum() or kulcs[0].isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A mező azonosítója csak betűt, számot és aláhúzást tartalmazhat, és nem kezdődhet számmal.",
        )
    if kulcs in model.__table__.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Már van '{kulcs}' nevű mező ezen az entitáson."
        )
    if kulcs in custom_keys(db, entity_type):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Már van '{kulcs}' nevű saját mező.")
    if field_type not in CUSTOM_FIELD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ismeretlen mezőtípus: {field_type}"
        )
    if field_type == "select" and not options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Legördülő mezőhöz legalább egy választható értéket adj meg."
        )

    utolso = max((d.sort_order for d in custom_defs(db, entity_type)), default=0)
    mezo = CustomFieldDef(
        entity_type=entity_type,
        field_key=kulcs,
        label=label.strip() or kulcs,
        field_type=field_type,
        options=[o for o in (options or []) if o.strip()] or None,
        sort_order=utolso + 1,
        created_by_employee_id=employee_id,
    )
    db.add(mezo)
    db.commit()
    db.refresh(mezo)
    return mezo


def delete_custom_field(db: Session, entity_type: str, field_key: str) -> None:
    """Saját mező végleges törlése - az összes rekordon tárolt értékével
    együtt. Ez valódi törlés: nincs mit elrejteni, a mező nem létezett a
    Notion-importban sem."""
    mezo = db.scalar(
        select(CustomFieldDef).where(CustomFieldDef.entity_type == entity_type, CustomFieldDef.field_key == field_key)
    )
    if mezo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen saját mező.")
    for row in db.scalars(
        select(CustomFieldValue).where(
            CustomFieldValue.entity_type == entity_type, CustomFieldValue.field_key == field_key
        )
    ):
        db.delete(row)
    db.delete(mezo)
    db.commit()
