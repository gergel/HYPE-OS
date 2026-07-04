from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.employee import Employee
from app.models.field_visibility import FieldVisibilityConfig
from app.schemas.field_visibility import FieldVisibilityRead, FieldVisibilityUpdate, MyFieldVisibility
from app.services.entity_registry import get_field_types

router = APIRouter(prefix="/field-visibility", tags=["field-visibility"])


@router.get("/schema/{entity_type}", dependencies=[Depends(get_current_user)])
def get_entity_field_types(entity_type: str, db: Session = Depends(get_db)):
    """{mezőnév: {"type": "boolean"|"date"|"datetime"|"number"|"select"|"text", "options"?: [...]}} -
    a frontend ebből tudja, hogy egy éppen null értékű mezőt checkbox-ként vagy
    dátum-inputként kell-e megjelenítenie, illetve mely mezők jelenjenek meg
    legördülő (select) listaként a lehetséges értékekkel (lásd EditableDetailGrid)."""
    return get_field_types(entity_type, db)


@router.get("/me/{entity_type}", response_model=MyFieldVisibility)
def get_my_field_visibility(entity_type: str, current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    """A bejelentkezett felhasználó saját mező-láthatósága egy entitástípushoz -
    ezt használják a részletnézet oldalak, hogy csak a neki engedélyezett
    mezőket jelenítsék meg. Nincs config sor -> minden mező látszik."""
    config = db.scalar(
        select(FieldVisibilityConfig).where(
            FieldVisibilityConfig.employee_id == current_user.id, FieldVisibilityConfig.entity_type == entity_type
        )
    )
    return MyFieldVisibility(visible_fields=config.visible_fields if config else None)


@router.get("", response_model=list[FieldVisibilityRead], dependencies=[Depends(require_roles(Role.ADMIN))])
def list_all_field_visibility(db: Session = Depends(get_db)):
    """Az összes munkatárs összes entitástípushoz beállított mező-láthatósága,
    egyetlen lekérdezéssel (Beállítások oldal) - fontos, hogy EGY hívás legyen
    munkatársanként N hívás helyett, mert utóbbi (sok munkatárs esetén,
    párhuzamosan hívva) kimeríti a DB connection pool-t (QueuePool timeout)."""
    return db.scalars(select(FieldVisibilityConfig)).all()


@router.get("/{employee_id}", response_model=list[FieldVisibilityRead], dependencies=[Depends(require_roles(Role.ADMIN))])
def list_field_visibility(employee_id: int, db: Session = Depends(get_db)):
    """Egy adott munkatárs összes entitástípushoz beállított mező-láthatósága
    (Beállítások oldal tölti be, amikor admin kiválaszt egy munkatársat)."""
    return db.scalars(select(FieldVisibilityConfig).where(FieldVisibilityConfig.employee_id == employee_id)).all()


@router.put(
    "/{employee_id}/{entity_type}",
    response_model=FieldVisibilityRead,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def set_field_visibility(employee_id: int, entity_type: str, payload: FieldVisibilityUpdate, db: Session = Depends(get_db)):
    """Admin beállítja, mely mezők látszanak egy adott munkatársnak egy adott
    entitástípusnál - egyénenként, csak admin szerkesztheti. visible_fields=null
    vagy [] törli a szűrést (a munkatárs újra minden mezőt lát)."""
    config = db.scalar(
        select(FieldVisibilityConfig).where(
            FieldVisibilityConfig.employee_id == employee_id, FieldVisibilityConfig.entity_type == entity_type
        )
    )
    if config is None:
        config = FieldVisibilityConfig(employee_id=employee_id, entity_type=entity_type, visible_fields=payload.visible_fields)
        db.add(config)
    else:
        config.visible_fields = payload.visible_fields
    db.commit()
    db.refresh(config)
    return config
