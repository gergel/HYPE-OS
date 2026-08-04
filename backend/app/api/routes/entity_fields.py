"""Mezőkezelés: a Notionből áthozott, itt már felesleges mezők eltávolítása és
saját mezők létrehozása (Beállítások oldal, "Mezők" szekció).

Jogosultság: ADMIN szerepkör ÉS "delete" jog a Beállítások oldalon - ez a
rendszer szerkezetét változtatja, nem egy rekord adatát, ezért szigorúbb, mint
egy sima szerkesztés."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, check_page_action, get_current_user, require_roles
from app.models.employee import Employee
from app.services import entity_fields
from app.services.entity_registry import ENTITY_MODELS, get_field_types

router = APIRouter(prefix="/entity-fields", tags=["entity-fields"])

BEALLITASOK_PAGE = "/beallitasok"


def mezokezelo(
    current_user: Employee = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)
) -> Employee:
    """Admin szerepkör ÉS törlési jog a Beállítások oldalon."""
    check_page_action(db, current_user, BEALLITASOK_PAGE, "delete")
    return current_user


class FieldInfo(BaseModel):
    """Egy mező az entitáson - akár valódi oszlop, akár saját mező."""

    name: str
    label: str
    type: str
    options: list[str] | None = None
    #: Saját (admin által létrehozott) mező-e - csak ezek törölhetők véglegesen.
    custom: bool = False
    #: Eltávolítva a rendszerből (csak valódi mezőnél fordulhat elő).
    removed: bool = False
    #: Az eltávolításkor az adatait is kiürítettük-e.
    data_wiped: bool = False
    #: Eltávolítható-e egyáltalán (a kötelező és rendszer-mezők nem).
    removable: bool = True
    #: Miért nem távolítható el.
    reason: str | None = None


class EntityFieldsRead(BaseModel):
    entity_type: str
    fields: list[FieldInfo]


class RemoveFieldIn(BaseModel):
    field_name: str
    #: Ürítse-e ki a mezőben tárolt adatokat is. Ez visszavonhatatlan.
    wipe_data: bool = False


class CustomFieldIn(BaseModel):
    field_key: str
    label: str
    field_type: str = "text"
    options: list[str] | None = None


@router.get("/entities", dependencies=[Depends(get_current_user)])
def list_entities() -> list[str]:
    """Mely entitástípusokon kezelhetők a mezők (lásd ENTITY_MODELS)."""
    return sorted(ENTITY_MODELS.keys())


@router.get("/{entity_type}", response_model=EntityFieldsRead, dependencies=[Depends(get_current_user)])
def list_fields(entity_type: str, db: Session = Depends(get_db)):
    """Az entitás ÖSSZES mezője - az eltávolítottakkal együtt, hogy a
    Beállítások oldalon vissza is lehessen hozni őket."""
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ismeretlen entitástípus: {entity_type}")

    eltavolitott = {
        c.field_name: c
        for c in db.query(entity_fields.EntityFieldConfig).filter_by(entity_type=entity_type).all()
    }
    # A típusokat a meglévő mezőtípus-szolgáltatás adja (az eltávolítottak
    # nélkül) - az eltávolítottakhoz nem is kell típus, csak a visszahozáshoz
    # a nevük.
    tipusok = get_field_types(entity_type, db)

    mezok: list[FieldInfo] = []
    for name, column in model.__table__.columns.items():
        info = tipusok.get(name, {"type": "text"})
        removable, reason = True, None
        if name in entity_fields.PROTECTED_FIELDS:
            removable, reason = False, "A rendszer működéséhez kell."
        elif column.primary_key or not column.nullable:
            removable, reason = False, "Kötelező mező."
        config = eltavolitott.get(name)
        mezok.append(
            FieldInfo(
                name=name,
                label=name,
                type=info.get("type", "text"),
                options=info.get("options"),
                removed=bool(config and config.hidden),
                data_wiped=bool(config and config.data_wiped),
                removable=removable,
                reason=reason,
            )
        )

    for mezo in entity_fields.custom_defs(db, entity_type):
        mezok.append(
            FieldInfo(
                name=mezo.field_key,
                label=mezo.label,
                type=mezo.field_type,
                options=list(mezo.options or []) or None,
                custom=True,
            )
        )

    return EntityFieldsRead(entity_type=entity_type, fields=mezok)


@router.post("/{entity_type}/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_field(
    entity_type: str,
    payload: RemoveFieldIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(mezokezelo),
):
    """Mező eltávolítása a rendszerből. wipe_data=true esetén a benne tárolt
    adatokat is kiüríti - az visszavonhatatlan."""
    entity_fields.remove_field(
        db, entity_type, payload.field_name, wipe_data=payload.wipe_data, employee_id=current_user.id
    )


@router.post("/{entity_type}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_field(
    entity_type: str,
    payload: RemoveFieldIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(mezokezelo),
):
    """Korábban eltávolított mező visszahozása (üresen, ha az adatait kiürítettük)."""
    entity_fields.restore_field(db, entity_type, payload.field_name)


@router.post("/{entity_type}/custom", response_model=FieldInfo, status_code=status.HTTP_201_CREATED)
def create_custom_field(
    entity_type: str,
    payload: CustomFieldIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(mezokezelo),
):
    """Új, saját mező létrehozása. Azonnal megjelenik a rekordok adatlapján, és
    ugyanúgy szerkeszthető, mint bármelyik eredeti mező."""
    mezo = entity_fields.create_custom_field(
        db,
        entity_type,
        field_key=payload.field_key,
        label=payload.label,
        field_type=payload.field_type,
        options=payload.options,
        employee_id=current_user.id,
    )
    return FieldInfo(
        name=mezo.field_key,
        label=mezo.label,
        type=mezo.field_type,
        options=list(mezo.options or []) or None,
        custom=True,
    )


@router.delete("/{entity_type}/custom/{field_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_field(
    entity_type: str, field_key: str, db: Session = Depends(get_db), _user: Employee = Depends(mezokezelo)
):
    """Saját mező végleges törlése, az összes rekordon tárolt értékével együtt."""
    entity_fields.delete_custom_field(db, entity_type, field_key)
