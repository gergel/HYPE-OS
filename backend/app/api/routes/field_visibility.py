from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.field_visibility import FieldVisibilityConfig
from app.schemas.field_visibility import FieldVisibilityRead, FieldVisibilityUpdate
from app.services.entity_registry import get_field_types

router = APIRouter(prefix="/field-visibility", tags=["field-visibility"])


@router.get("/{entity_type}/schema")
def get_entity_field_types(entity_type: str):
    """{mezőnév: "boolean"|"date"|"datetime"|"number"|"text"} - a frontend ebből
    tudja, hogy egy éppen null értékű mezőt checkbox-ként vagy dátum-inputként
    kell-e megjelenítenie (a nyers null értékből ez nem derülne ki)."""
    return get_field_types(entity_type)


@router.get("", response_model=list[FieldVisibilityRead])
def list_field_visibility(db: Session = Depends(get_db)):
    """Az összes entitástípushoz beállított mező-láthatóság (Beállítások oldal
    tölti be egyszerre mindet). Amihez nincs config sor, ott nincs szűrés
    (minden mező látszik) - a frontend ezt üres listaként kezeli."""
    return db.scalars(select(FieldVisibilityConfig)).all()


@router.put(
    "/{entity_type}",
    response_model=FieldVisibilityRead,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def set_field_visibility(entity_type: str, payload: FieldVisibilityUpdate, db: Session = Depends(get_db)):
    """Beállítja, mely mezők látszanak az adott entitástípus részletnézetén -
    mindenkire egyformán vonatkozik (nem személyre szabott). visible_fields=null
    vagy [] törli a szűrést (minden mező újra látszik)."""
    config = db.scalar(select(FieldVisibilityConfig).where(FieldVisibilityConfig.entity_type == entity_type))
    if config is None:
        config = FieldVisibilityConfig(entity_type=entity_type, visible_fields=payload.visible_fields)
        db.add(config)
    else:
        config.visible_fields = payload.visible_fields
    db.commit()
    db.refresh(config)
    return config
