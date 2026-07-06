"""AI Assistant - Anthropic Claude tool-calling réteg a végleges Postgres felett.

Minden felhasználó a SAJÁT page_permissions/field_visibility jogosultsága szerint
lát rá az adatra: a tool-végrehajtás ugyanazt a check_page_action-t (lásd
core/security.py) és FieldVisibilityConfig-ot (lásd models/field_visibility.py)
használja, amit a többi CRUD végpont is - az asszisztens tehát sosem
mondhat el a felhasználónak olyat, amit a UI-n keresztül maga se látna.

A modell nem kap közvetlen DB-hozzáférést: kizárólag a lenti három tool-on
(list_entity_types/describe_entity/query_entity) keresztül ér el adatot, és
minden egyes tool-hívásnál újra lefut a jogosultság-ellenőrzés (nem elég, hogy
list_entity_types nem sorolja fel a tiltott típust - a modell akkor is
megpróbálhatná közvetlenül hívni)."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import check_page_action
from app.models.employee import Employee
from app.models.field_visibility import FieldVisibilityConfig
from app.services.entity_registry import ENTITY_MODELS, get_field_types

# entity_type (lásd entity_registry.ENTITY_MODELS) -> jogosultsági "oldal"
# (lásd frontend/lib/nav.ts pagePermissionGroups topSegmentjei, amit
# check_page_action is használ) - ez dönti el, melyik entitástípust nézheti
# meg az asszisztens az adott felhasználó nevében.
ENTITY_PAGES: dict[str, str] = {
    "project": "/projektek",
    "projectCode": "/projektek",
    "client": "/ugyfelek",
    "employee": "/csapat",
    "equipment": "/felszereles",
    "campaign": "/kampanyok",
    "task": "/feladatok",
    "expense": "/penzugyek",
    "revenue": "/penzugyek",
    "deliverable": "/utomunka",
}

MAX_ROWS = 50
MAX_TOOL_ROUNDS = 8


def _allowed_entity_types(db: Session, employee: Employee) -> list[str]:
    allowed = []
    for entity_type, page in ENTITY_PAGES.items():
        try:
            check_page_action(db, employee, page, "view")
        except Exception:
            continue
        allowed.append(entity_type)
    return allowed


def _visible_fields(db: Session, employee: Employee, entity_type: str, all_fields: list[str]) -> list[str]:
    config = db.scalar(
        select(FieldVisibilityConfig).where(
            FieldVisibilityConfig.employee_id == employee.id,
            FieldVisibilityConfig.entity_type == entity_type,
        )
    )
    if config is None or not config.visible_fields:
        return all_fields
    return [f for f in all_fields if f in config.visible_fields]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


_TRUE_STRINGS = {"true", "igen", "1", "yes"}
_FALSE_STRINGS = {"false", "nem", "0", "no"}


def _coerce_filter_value(py_type: type | None, value: Any) -> Any:
    """A modell tool-hívásának filters mezőjében az érték szinte mindig
    string (a JSON-séma nem ír elő per-mező típust) - dátum/szám/bool
    oszlopoknál viszont egy nyers string == összehasonlítás a Python str
    típusa alapján rossz SQL-típussal (pl. VARCHAR) kötné be a paramétert
    (SQLAlchemy a bind literál típusából indul ki, NEM az oszlopéból), ami
    Postgres-en "operator does not exist: date = character varying"-szerű
    hibát ad - ezért itt az oszlop tényleges Python típusára alakítjuk,
    mielőtt összehasonlítanánk. None visszatérés = nem sikerült értelmezni,
    ilyenkor a hívó inkább figyelmen kívül hagyja ezt a szűrőt."""
    if not isinstance(value, str):
        return value
    if py_type is date:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    if py_type is datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    if py_type is bool:
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
        return None
    if py_type in (int, float):
        try:
            return py_type(value)
        except ValueError:
            return None
    return value


def _describe_entity(db: Session, employee: Employee, entity_type: str) -> dict:
    if entity_type not in _allowed_entity_types(db, employee):
        return {"error": f"Nincs jogosultságod ehhez az entitástípushoz: {entity_type}"}
    field_types = get_field_types(entity_type, db)
    fields = _visible_fields(db, employee, entity_type, list(field_types.keys()))
    return {"fields": {name: field_types[name] for name in fields}}


def _query_entity(db: Session, employee: Employee, entity_type: str, filters: dict[str, Any] | None, limit: int) -> dict:
    if entity_type not in _allowed_entity_types(db, employee):
        return {"error": f"Nincs jogosultságod ehhez az entitástípushoz: {entity_type}"}
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return {"error": f"Ismeretlen entitástípus: {entity_type}"}

    columns = model.__table__.columns
    all_fields = list(columns.keys())
    visible = set(_visible_fields(db, employee, entity_type, all_fields))
    if not visible:
        return {"rows": [], "count": 0}

    query = select(model)
    for key, value in (filters or {}).items():
        if key not in columns or key not in visible:
            continue
        column = columns[key]
        # ILIKE csak valódi szöveges oszlopokon értelmezhető (Postgres nem tud
        # "date ~~* varchar"-t) - más típusoknál (dátum, szám, bool, enum stb.)
        # egyenlőséget használunk, a szöveges JSON-értéket pedig előbb az
        # oszlop tényleges Python típusára alakítjuk (lásd _coerce_filter_value).
        py_type = getattr(column.type, "python_type", None)
        if py_type is str and isinstance(value, str):
            query = query.where(column.ilike(f"%{value}%"))
            continue
        coerced = _coerce_filter_value(py_type, value)
        if coerced is None:
            # Nem sikerült értelmezni (pl. hibás dátumformátum) - inkább
            # figyelmen kívül hagyjuk ezt a szűrőt, mint hogy 500-at dobjunk.
            continue
        query = query.where(column == coerced)

    query = query.limit(max(1, min(limit or 20, MAX_ROWS)))
    try:
        rows = db.scalars(query).all()
    except Exception as exc:
        # Egy rosszul formázott szűrő (pl. típus-eltérés) ne dobjon 500-at a
        # végpontból - a modell kapjon vissza egy hibaüzenetet, amiből tud
        # próbálkozni másképp. A rollback azért kell, mert egy sikertelen
        # SQL statement után a session tranzakciója "aborted" állapotba kerül,
        # ami a tool-loop KÖVETKEZŐ körének lekérdezéseit is elrontaná.
        db.rollback()
        return {"error": f"Sikertelen lekérdezés: {exc}"}
    result = [{field: _jsonable(getattr(row, field)) for field in all_fields if field in visible} for row in rows]
    return {"rows": result, "count": len(result)}


TOOLS: list[dict] = [
    {
        "name": "list_entity_types",
        "description": (
            "Visszaadja, mely adattípusokat (entitásokat) nézheti meg ez a felhasználó "
            "(pl. project, client, employee, equipment, campaign, task, expense, revenue, "
            "deliverable) - EZZEL kezdd, mielőtt bármit lekérdezel."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "describe_entity",
        "description": (
            "Visszaadja egy entitástípus mezőit és típusait (a felhasználónak ténylegesen "
            "látható mezőkre szűrve) - ebből tudod, milyen mezők szerint lehet szűrni/lekérdezni."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"entity_type": {"type": "string"}},
            "required": ["entity_type"],
        },
    },
    {
        "name": "query_entity",
        "description": (
            f"Lekérdez legfeljebb {MAX_ROWS} sort egy entitástípusból, opcionális mező=érték "
            "szűrőkkel (szöveges mezőknél részleges egyezés, egyébként pontos egyezés). Csak a "
            "felhasználó számára látható mezőket adja vissza."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string"},
                "filters": {"type": "object", "description": "mező -> érték párok"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["entity_type"],
        },
    },
]


def _execute_tool(db: Session, employee: Employee, name: str, tool_input: dict) -> dict:
    if name == "list_entity_types":
        return {"entity_types": _allowed_entity_types(db, employee)}
    if name == "describe_entity":
        return _describe_entity(db, employee, tool_input.get("entity_type", ""))
    if name == "query_entity":
        return _query_entity(
            db, employee, tool_input.get("entity_type", ""), tool_input.get("filters"), tool_input.get("limit", 20)
        )
    return {"error": f"Ismeretlen tool: {name}"}


SYSTEM_PROMPT = (
    "Te vagy a HYPE OS AI Assistant. A HYPE Productions belső gyártásmenedzsment-"
    "rendszerének adatai felett válaszolsz kérdésekre a list_entity_types/describe_entity/"
    "query_entity eszközök segítségével - ezeken kívül nincs más adathozzáférésed. "
    "FONTOS: kizárólag azokhoz az adatokhoz férsz hozzá, amiket a kérdező felhasználó "
    "jogosultsága megenged - ha egy eszköz jogosultsági hibát ad vissza, mondd el ezt "
    "őszintén a felhasználónak, ne próbáld megkerülni és ne találj ki adatot. "
    "Magyarul válaszolj, tömören és konkrétan."
)


def ask(db: Session, employee: Employee, question: str) -> str:
    if not settings.anthropic_api_key:
        return "Az AI Assistant nincs beállítva (hiányzik az ANTHROPIC_API_KEY)."

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages: list[dict] = [{"role": "user", "content": question}]

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                return "".join(block.text for block in response.content if block.type == "text").strip() or (
                    "Nem érkezett válasz szöveg."
                )

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = _execute_tool(db, employee, block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
    except anthropic.AuthenticationError:
        return "Az AI Assistant hitelesítési hibába ütközött (érvénytelen ANTHROPIC_API_KEY)."
    except anthropic.RateLimitError:
        return "Az AI Assistant túlterhelt (rate limit) - próbáld újra kicsit később."
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        return f"Az AI Assistant nem érhető el (hálózati/API hiba): {exc}"

    return "Nem sikerült választ generálni (túl sok lépés)."
