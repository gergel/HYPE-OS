"""Generikus CRUD router factory - list/get/create/update/delete végpontokat épít
egy SQLAlchemy modellre és a hozzá tartozó Pydantic sémákra, hogy a 20+ entitáshoz
ne kelljen ugyanazt a boilerplate-et kézzel megismételni minden modulban.
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, require_roles


def build_crud_router(
    *,
    model: type,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    prefix: str,
    tags: list[str],
    write_roles: tuple[Role, ...] = (Role.ADMIN, Role.OPERATOR),
    before_create: Callable[[dict, Session], dict] | None = None,
    m2m_fields: dict[str, tuple[str, type]] | None = None,
) -> APIRouter:
    """m2m_fields: {payload_key: (relationship_attr_name, related_model)} a many-to-many mezőkhöz
    (pl. Project.crew_employee_ids -> ("crew", Employee)), amiket a sima **data konstruktor nem tud kezelni.
    """
    router = APIRouter(prefix=prefix, tags=tags)
    write_dependency = require_roles(*write_roles) if write_roles else None
    m2m_fields = m2m_fields or {}

    def _get_or_404(db: Session, obj_id: int) -> Any:
        obj = db.get(model, obj_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} nem található")
        return obj

    def _apply_m2m(obj: Any, data: dict, db: Session) -> None:
        for payload_key, (attr_name, related_model) in m2m_fields.items():
            if payload_key not in data:
                continue
            ids = data.pop(payload_key)
            related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
            setattr(obj, attr_name, related)

    @router.get("", response_model=list[read_schema])
    def list_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
        return db.scalars(select(model).offset(skip).limit(limit)).all()

    @router.get("/{item_id}", response_model=read_schema)
    def get_item(item_id: int, db: Session = Depends(get_db)):
        return _get_or_404(db, item_id)

    create_kwargs = {"dependencies": [Depends(write_dependency)]} if write_dependency else {}

    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED, **create_kwargs)
    def create_item(payload: create_schema, db: Session = Depends(get_db)):
        data = payload.model_dump()
        m2m_data = {k: data.pop(k) for k in list(m2m_fields) if k in data}
        if before_create:
            data = before_create(data, db)
        obj = model(**data)
        for payload_key, ids in m2m_data.items():
            attr_name, related_model = m2m_fields[payload_key]
            related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
            setattr(obj, attr_name, related)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.patch("/{item_id}", response_model=read_schema, **create_kwargs)
    def update_item(item_id: int, payload: update_schema, db: Session = Depends(get_db)):
        obj = _get_or_404(db, item_id)
        data = payload.model_dump(exclude_unset=True)
        for payload_key in list(m2m_fields):
            if payload_key in data:
                ids = data.pop(payload_key)
                attr_name, related_model = m2m_fields[payload_key]
                related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
                setattr(obj, attr_name, related)
        for field, value in data.items():
            setattr(obj, field, value)
        db.commit()
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, **create_kwargs)
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        obj = _get_or_404(db, item_id)
        db.delete(obj)
        db.commit()

    return router
