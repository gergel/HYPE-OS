from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.detail_section_order import DetailSectionOrder
from app.models.detail_tab import DetailTabConfig
from app.models.employee import Employee
from app.schemas.detail_tab import DetailTabConfigRead, DetailTabConfigWrite, DetailTabRead
from app.services import detail_tabs as detail_tabs_service

router = APIRouter(prefix="/detail-tabs", tags=["detail-tabs"])


class SectionOrderPayload(BaseModel):
    section_keys: list[str]


@router.get("", response_model=list[DetailTabConfigRead])
def list_all_tab_configs(
    db: Session = Depends(get_db), _admin: Employee = Depends(require_roles(Role.ADMIN))
):
    """Minden entitástípus fül-elrendezése egyszerre (Beállítások oldal admin
    fül-szerkesztője tölti be egyben)."""
    rows = db.scalars(select(DetailTabConfig).order_by(DetailTabConfig.entity_type, DetailTabConfig.sort_order)).all()
    by_entity: dict[str, list[DetailTabConfig]] = {}
    for row in rows:
        by_entity.setdefault(row.entity_type, []).append(row)
    return [
        DetailTabConfigRead(entity_type=entity_type, tabs=[DetailTabRead.model_validate(t) for t in tabs])
        for entity_type, tabs in by_entity.items()
    ]


@router.get("/{entity_type}", response_model=list[DetailTabRead])
def get_tab_config(entity_type: str, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Egy entitástípus fül-elrendezése - bármely bejelentkezett felhasználó
    lekérdezheti (a részletnézetek ez alapján rendereződnek), de nem
    módosíthatja."""
    return detail_tabs_service.get_tabs(db, entity_type)


@router.put("/{entity_type}", response_model=list[DetailTabRead])
def set_tab_config(
    entity_type: str,
    payload: DetailTabConfigWrite,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_roles(Role.ADMIN)),
):
    """Admin felülírja egy entitástípus teljes fül-listáját (Beállítások
    oldal) - a korábbi fülek törlődnek, az újak lépnek a helyükre."""
    return detail_tabs_service.replace_tabs(db, entity_type, payload.tabs)


@router.get("/{entity_type}/section-order", response_model=SectionOrderPayload)
def get_section_order(
    entity_type: str, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
) -> SectionOrderPayload:
    """A részletnézet szekció-kártyáinak sorrendje - bármely bejelentkezett
    felhasználó lekérdezheti, mert minden részletnézet ez alapján rendeződik."""
    row = db.scalars(select(DetailSectionOrder).where(DetailSectionOrder.entity_type == entity_type)).first()
    return SectionOrderPayload(section_keys=row.section_keys if row else [])


@router.put("/{entity_type}/section-order", response_model=SectionOrderPayload)
def set_section_order(
    entity_type: str,
    payload: SectionOrderPayload,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_roles(Role.ADMIN)),
) -> SectionOrderPayload:
    """Az új sorrend mentése (húzással átrendezés után) - entitástípusonként
    EGY közös sorrend, tehát az adott típus minden rekordjánál ez érvényesül,
    pontosan úgy, ahogy az admin beállította."""
    row = db.scalars(select(DetailSectionOrder).where(DetailSectionOrder.entity_type == entity_type)).first()
    if row is None:
        row = DetailSectionOrder(entity_type=entity_type, section_keys=payload.section_keys)
        db.add(row)
    else:
        row.section_keys = payload.section_keys
    db.commit()
    return SectionOrderPayload(section_keys=row.section_keys)
