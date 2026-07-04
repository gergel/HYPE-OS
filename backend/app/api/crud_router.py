"""Generikus CRUD router factory - list/get/create/update/delete végpontokat épít
egy SQLAlchemy modellre és a hozzá tartozó Pydantic sémákra, hogy a 20+ entitáshoz
ne kelljen ugyanazt a boilerplate-et kézzel megismételni minden modulban.
"""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.employee import Employee

# Soha nem PATCH-elhető mezők, még akkor sem, ha valódi oszlopok - a "minden
# adat szerkeszthető" elv alól ez az egyetlen kivétel (biztonsági okból).
_PATCH_DENYLIST = {"id", "hashed_password"}


def _coerce_value(column: Any, value: Any) -> Any:
    """A böngészőből érkező nyers JSON értéket (string/number/bool/null) az
    oszlop tényleges Python típusára alakítja, ahol ez nem triviális (Date/
    DateTime oszlopok stringként érkeznek az inline-szerkesztő inputokból)."""
    if value is None or not isinstance(value, str):
        return value
    py_type = getattr(column.type, "python_type", None)
    if py_type is date:
        return date.fromisoformat(value[:10])
    if py_type is datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


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
    list_read_schema: type[BaseModel] | None = None,
    after_update: Callable[[Any, dict, dict[str, dict[str, set[int]]], Session, Employee], None] | None = None,
) -> APIRouter:
    """m2m_fields: {payload_key: (relationship_attr_name, related_model)} a many-to-many mezőkhöz
    (pl. Project.crew_employee_ids -> ("crew", Employee)), amiket a sima **data konstruktor nem tud kezelni.

    update_schema: jelenleg nem használja a PATCH végpont ("minden mező helyben
    szerkeszthető" - lásd update_item) - az a nyers JSON body-t fogadja és
    bármelyik valódi oszlopot elfogadja, hogy ne kelljen entitásonként kézzel
    karban tartani egy 50-140 mezős Update sémát. A paraméter a hívási helyeken
    (routes/*.py) marad, hogy ne kelljen mindet átírni, és mert dokumentálja,
    milyen mezőkre gondolt eredetileg az adott entitás Update DTO-ja.

    list_read_schema: ha meg van adva, a lista végpont (GET "") ezt a szűkebb sémát
    használja read_schema helyett - nagyon széles táblákhoz (pl. Project ~140 oszlop),
    ahol a listanézet ténylegesen csak pár mezőt jelenít meg, de a teljes séma
    soronkénti validálása/JSON-ba szerializálása felesleges terhelés minden egyes
    listaoldal-betöltésnél. Az egyedi rekord GET továbbra is a teljes read_schema-t adja.

    after_update: PATCH után hívódik (obj, data, m2m_changes, db, current_user) paraméterekkel,
    miután a rekord már commitolva/refresh-elve van - side effect-ekhez (pl. értesítés
    küldése kiosztás-váltáskor, lásd routes/postproduction.py, routes/tasks.py). `data` a
    ténylegesen PATCH-elt scalar mezőket tartalmazza (a payload kulcsaival), `m2m_changes`
    pedig {payload_key: {"added": {id, ...}, "removed": {id, ...}}} minden érintett m2m mezőhöz."""
    router = APIRouter(prefix=prefix, tags=tags)
    write_dependency = require_roles(*write_roles) if write_roles else None
    m2m_fields = m2m_fields or {}
    list_read_schema = list_read_schema or read_schema

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

    column_names = set(model.__table__.columns.keys())

    @router.get("", response_model=list[list_read_schema])
    def list_items(
        request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
    ):
        """A skip/limit mellett bármelyik valódi oszlop szerint szűrhető query
        param-mal (pl. ?project_code_id=5) - ez adja a kapcsolódó rekordok
        (pl. egy Project Code összes Projektje) frontend-oldali lekérdezését.
        Bejelentkezés nélkül semmilyen adat nem érhető el (lásd get_current_user)."""
        stmt = select(model)
        for key, raw_value in request.query_params.items():
            if key in ("skip", "limit") or key not in column_names:
                continue
            try:
                value: Any = int(raw_value)
            except ValueError:
                value = raw_value
            stmt = stmt.where(getattr(model, key) == value)
        return db.scalars(stmt.offset(skip).limit(limit)).all()

    @router.get("/{item_id}", response_model=read_schema)
    def get_item(item_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
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

    update_user_dependency = write_dependency or get_current_user

    @router.patch("/{item_id}", response_model=read_schema)
    async def update_item(
        item_id: int,
        request: Request,
        db: Session = Depends(get_db),
        current_user: Employee = Depends(update_user_dependency),
    ):
        """A payload egy nyers JSON objektum (nem egy fix update_schema) - bármelyik
        valódi oszlop PATCH-elhető vele (a hashed_password/id kivételével), hogy a
        részletnézeten bármelyik mező helyben szerkeszthető legyen (lásd
        EditableDetailGrid a frontenden), anélkül hogy minden entitáshoz kézzel
        karban kellene tartani egy külön Update sémát a ~50-140 mezőhöz."""
        obj = _get_or_404(db, item_id)
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A kérés törzsének JSON objektumnak kell lennie")

        m2m_changes: dict[str, dict[str, set[int]]] = {}
        for payload_key in list(m2m_fields):
            if payload_key in data:
                ids = set(data.pop(payload_key) or [])
                attr_name, related_model = m2m_fields[payload_key]
                previous_ids = {r.id for r in getattr(obj, attr_name)}
                related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
                setattr(obj, attr_name, related)
                m2m_changes[attr_name] = {"added": ids - previous_ids, "removed": previous_ids - ids}

        columns = model.__table__.columns
        for field, value in data.items():
            if field in _PATCH_DENYLIST or field not in column_names:
                continue
            try:
                setattr(obj, field, _coerce_value(columns[field], value))
            except (ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Érvénytelen érték a '{field}' mezőhöz: {exc}"
                ) from exc
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Az érték már foglalt (egyedinek kell lennie)."
            ) from exc
        db.refresh(obj)
        if after_update:
            after_update(obj, data, m2m_changes, db, current_user)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, **create_kwargs)
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        obj = _get_or_404(db, item_id)
        db.delete(obj)
        db.commit()

    return router
