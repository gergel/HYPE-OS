from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detail_tab import DetailTabConfig
from app.schemas.detail_tab import DetailTabWrite

# A szintetikus "Egyéb" fül kulcsa - minden mező, amit admin egyetlen
# konfigurált fülhöz sem rendelt hozzá, ide esik (lásd DetailTabConfig
# osztály-kommentje) - fül-szintű jogosultság-ellenőrzésnél is ez a kulcs
# szerepel a "{page}:{tab_key}" összetett kulcsban.
OTHER_TAB_KEY = "_other"


def get_tabs(db: Session, entity_type: str) -> list[DetailTabConfig]:
    return list(
        db.scalars(
            select(DetailTabConfig).where(DetailTabConfig.entity_type == entity_type).order_by(DetailTabConfig.sort_order)
        )
    )


def get_field_tab_map(db: Session, entity_type: str) -> dict[str, str]:
    """{mezőnév: fül_kulcs} - amit egyik konfigurált fül sem tartalmaz, azt a
    hívó (pl. crud_router update_item) OTHER_TAB_KEY-ként kezelje."""
    result: dict[str, str] = {}
    for tab in get_tabs(db, entity_type):
        for field_key in tab.field_keys or []:
            result[field_key] = tab.tab_key
    return result


def replace_tabs(db: Session, entity_type: str, tabs: list[DetailTabWrite]) -> list[DetailTabConfig]:
    db.query(DetailTabConfig).filter(DetailTabConfig.entity_type == entity_type).delete()
    rows = [
        DetailTabConfig(
            entity_type=entity_type,
            tab_key=t.tab_key,
            label=t.label,
            icon=t.icon,
            sort_order=index,
            field_keys=t.field_keys,
        )
        for index, t in enumerate(tabs)
    ]
    db.add_all(rows)
    db.commit()
    return get_tabs(db, entity_type)
