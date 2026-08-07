"""AI Assistant - Google Gemini function-calling réteg a végleges Postgres felett.

Minden felhasználó a SAJÁT page_permissions/field_visibility jogosultsága szerint
lát rá az adatra: a tool-végrehajtás ugyanazt a check_page_action-t (lásd
core/security.py) és FieldVisibilityConfig-ot (lásd models/field_visibility.py)
használja, amit a többi CRUD végpont is - az asszisztens tehát sosem
mondhat el a felhasználónak olyat, amit a UI-n keresztül maga se látna.

A modell nem kap közvetlen DB-hozzáférést: kizárólag a lenti tool-okon
(list_entity_types/describe_entity/query_entity/aggregate_entity) keresztül
ér el adatot, és minden egyes tool-hívásnál újra lefut a jogosultság-
ellenőrzés (nem elég, hogy list_entity_types nem sorolja fel a tiltott
típust - a modell akkor is megpróbálhatná közvetlenül hívni).

Az elérhető entitástípusokat és mezőiket a rendszerüzenetbe már előre
beleírjuk (lásd _build_system_prompt) - ez azért fontos, mert enélkül a
modell szinte minden kérdésnél előbb list_entity_types-t, majd
describe_entity-t hívna, ami két plusz Gemini API oda-vissza kört (több
másodperc) jelentene minden egyes kérdésnél. Az aggregate_entity tool pedig
azért létezik query_entity mellett, mert egy összeg/átlag/darabszám/
minimum/maximum kérdésre a helyes válasz az ÖSSZES megfelelő rekordon
számolt SQL-aggregátum, nem csak a query_entity limitált (legfeljebb
MAX_ROWS soros) lapján látott részhalmaz maximuma."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from sqlalchemy import func, select
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

_AGG_FUNCS = {"count": func.count, "sum": func.sum, "avg": func.avg, "min": func.min, "max": func.max}


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


def _apply_filters(query, columns, visible: set[str], filters: dict[str, Any] | None):
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
    return query


def _describe_entity(db: Session, employee: Employee, entity_type: str) -> dict:
    if entity_type not in _allowed_entity_types(db, employee):
        return {"error": f"Nincs jogosultságod ehhez az entitástípushoz: {entity_type}"}
    field_types = get_field_types(entity_type, db)
    fields = _visible_fields(db, employee, entity_type, list(field_types.keys()))
    return {"fields": {name: field_types[name] for name in fields}}


def _query_entity(
    db: Session,
    employee: Employee,
    entity_type: str,
    filters: dict[str, Any] | None,
    limit: int,
    order_by: str | None = None,
    order_dir: str | None = None,
) -> dict:
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

    query = _apply_filters(select(model), columns, visible, filters)
    if order_by and order_by in columns and order_by in visible:
        column = columns[order_by]
        query = query.order_by(column.desc() if (order_dir or "").lower() == "desc" else column.asc())
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


def _aggregate_entity(
    db: Session,
    employee: Employee,
    entity_type: str,
    field: str | None,
    operation: str,
    filters: dict[str, Any] | None,
) -> dict:
    """SQL-szintű összesítés (count/sum/avg/min/max) az ÖSSZES megfelelő
    rekordon - nem csak a query_entity limitált lapján látott részhalmazon.
    Ez ad garantáltan helyes választ az "összesen mennyi", "legnagyobb/
    legkisebb", "átlagosan mennyi" jellegű kérdésekre."""
    if entity_type not in _allowed_entity_types(db, employee):
        return {"error": f"Nincs jogosultságod ehhez az entitástípushoz: {entity_type}"}
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return {"error": f"Ismeretlen entitástípus: {entity_type}"}
    if operation not in _AGG_FUNCS:
        return {"error": f"Ismeretlen művelet: {operation} (count/sum/avg/min/max valamelyike lehet)"}

    columns = model.__table__.columns
    all_fields = list(columns.keys())
    visible = set(_visible_fields(db, employee, entity_type, all_fields))

    if operation == "count":
        if not field:
            expr = func.count()
        elif field in columns and field in visible:
            expr = func.count(columns[field])
        else:
            return {"error": f"Nincs jogosultságod vagy nem létezik ez a mező: {field}"}
    else:
        if not field or field not in columns or field not in visible:
            return {"error": f"Nincs jogosultságod vagy nem létezik ez a mező: {field}"}
        expr = _AGG_FUNCS[operation](columns[field])

    query = _apply_filters(select(expr), columns, visible, filters)
    try:
        result = db.scalar(query)
    except Exception as exc:
        db.rollback()
        return {"error": f"Sikertelen aggregálás: {exc}"}
    return {"entity_type": entity_type, "field": field, "operation": operation, "result": _jsonable(result)}


# A Gemini function-calling sémája az OpenAPI részhalmaza: a szabad alakú
# "objektum" paramétert (tetszőleges mező -> érték szűrők) nem tudja leírni,
# ezért a filters JSON SZÖVEGKÉNT megy át, és mi olvassuk vissza (lásd
# _szurok). Cserébe a séma érvényes marad, és a modell is egyértelmű
# utasítást kap arról, mit várunk.
TOOLS: list[dict] = [
    {
        "name": "list_entity_types",
        "description": (
            "Visszaadja, mely adattípusokat (entitásokat) nézheti meg ez a felhasználó "
            "(pl. project, client, employee, equipment, campaign, task, expense, revenue, "
            "deliverable) - EZZEL kezdd, mielőtt bármit lekérdezel."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "describe_entity",
        "description": (
            "Visszaadja egy entitástípus mezőit és típusait (a felhasználónak ténylegesen "
            "látható mezőkre szűrve) - ebből tudod, milyen mezők szerint lehet szűrni/lekérdezni."
        ),
        "parameters": {
            "type": "object",
            "properties": {"entity_type": {"type": "string"}},
            "required": ["entity_type"],
        },
    },
    {
        "name": "query_entity",
        "description": (
            f"Lekérdez legfeljebb {MAX_ROWS} SORT egy entitástípusból, opcionális mező=érték "
            "szűrőkkel (szöveges mezőknél részleges egyezés, egyébként pontos egyezés) és "
            "rendezéssel (order_by/order_dir - pl. 'top N' listákhoz). Csak a felhasználó "
            "számára látható mezőket adja vissza. NE ezt használd összeg/átlag/darabszám/"
            "minimum/maximum kérdésekhez - arra az aggregate_entity a garantáltan helyes eszköz, "
            "mert az ÖSSZES megfelelő rekordra számol, nem csak az itt visszaadott lapra."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string"},
                "filters": {
                    "type": "string",
                    "description": 'JSON objektum szövegként: mező -> érték párok, pl. {"allapot": "Kész"}',
                },
                "limit": {"type": "integer", "description": "hány sort kérsz (alapértelmezés 20)"},
                "order_by": {"type": "string", "description": "melyik mező szerint rendezzen"},
                "order_dir": {"type": "string", "enum": ["asc", "desc"], "description": "alapértelmezés: asc"},
            },
            "required": ["entity_type"],
        },
    },
    {
        "name": "aggregate_entity",
        "description": (
            "Összesítést (count/sum/avg/min/max) számol egy entitástípus egy mezőjén, az ÖSSZES "
            "megfelelő rekordra (nem csak egy korlátozott lapra) - EZT használd 'összesen mennyi', "
            "'átlagosan mennyi', 'hány darab', 'legnagyobb/legkisebb' jellegű kérdéseknél a "
            "query_entity helyett, mert ez garantáltan helyes eredményt ad, függetlenül attól, "
            "hány rekord van."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string"},
                "field": {"type": "string", "description": "a számolandó mező neve (count esetén elhagyható)"},
                "operation": {"type": "string", "enum": ["count", "sum", "avg", "min", "max"]},
                "filters": {
                    "type": "string",
                    "description": 'JSON objektum szövegként: mező -> érték párok, pl. {"allapot": "Kész"}',
                },
            },
            "required": ["entity_type", "operation"],
        },
    },
]


def _szurok(ertek) -> dict | None:
    """A filters paraméter feloldása. A Gemini SZÖVEGKÉNT kapja (a sémája nem
    tud szabad alakú objektumot leírni), de ha mégis objektumot küldene, azt is
    elfogadjuk - a hibás JSON-t nem nyeljük el, hanem szólunk a modellnek."""
    if ertek in (None, ""):
        return None
    if isinstance(ertek, dict):
        return ertek
    try:
        ertelmezett = json.loads(str(ertek))
    except ValueError as exc:
        raise ValueError(f"A filters nem értelmezhető JSON objektumként: {exc}") from exc
    if not isinstance(ertelmezett, dict):
        raise ValueError("A filters JSON objektum kell legyen (mező -> érték párok).")
    return ertelmezett


def _execute_tool(db: Session, employee: Employee, name: str, tool_input: dict) -> dict:
    if name == "list_entity_types":
        return {"entity_types": _allowed_entity_types(db, employee)}
    if name == "describe_entity":
        return _describe_entity(db, employee, tool_input.get("entity_type", ""))
    if name == "query_entity":
        return _query_entity(
            db,
            employee,
            tool_input.get("entity_type", ""),
            _szurok(tool_input.get("filters")),
            tool_input.get("limit", 20),
            tool_input.get("order_by"),
            tool_input.get("order_dir"),
        )
    if name == "aggregate_entity":
        return _aggregate_entity(
            db,
            employee,
            tool_input.get("entity_type", ""),
            tool_input.get("field"),
            tool_input.get("operation", ""),
            _szurok(tool_input.get("filters")),
        )
    return {"error": f"Ismeretlen tool: {name}"}


_BASE_SYSTEM_PROMPT = (
    "Te vagy a HYPE OS AI Assistant. A HYPE Productions belső gyártásmenedzsment-"
    "rendszerének adatai felett válaszolsz kérdésekre a list_entity_types/describe_entity/"
    "query_entity/aggregate_entity eszközök segítségével - ezeken kívül nincs más "
    "adathozzáférésed. FONTOS: kizárólag azokhoz az adatokhoz férsz hozzá, amiket a kérdező "
    "felhasználó jogosultsága megenged - ha egy eszköz jogosultsági hibát ad vissza, mondd el "
    "ezt őszintén a felhasználónak, ne próbáld megkerülni és ne találj ki adatot. Összeg/átlag/"
    "darabszám/minimum/maximum jellegű kérdésnél MINDIG az aggregate_entity-t használd, ne a "
    "query_entity korlátozott lapján próbálj magad számolni/becsülni. Magyarul válaszolj, "
    "tömören és konkrétan."
)


def _build_system_prompt(db: Session, employee: Employee) -> str:
    """Az elérhető entitástípusokat és mezőiket előre beleírjuk a rendszerüzenetbe, hogy a
    modellnek ne kelljen (majdnem) minden kérdésnél előbb list_entity_types-t, majd
    describe_entity-t hívnia egy külön-külön Gemini API oda-vissza körrel (ez kérdésenként
    több másodperc plusz válaszidőt jelentett). get_field_types itt db nélkül fut, hogy a
    szöveges mezők select-heurisztikája (ami saját DB-lekérdezésekkel járna) ne fusson le
    minden egyes kérdésnél - csak mező név+típus kell ide, a pontos select-értékekhez a modell
    továbbra is hívhatja a describe_entity tool-t."""
    lines = []
    for entity_type in _allowed_entity_types(db, employee):
        field_types = get_field_types(entity_type)
        fields = _visible_fields(db, employee, entity_type, list(field_types.keys()))
        field_descr = ", ".join(f"{f}:{field_types[f]['type']}" for f in fields)
        lines.append(f"- {entity_type}: {field_descr}")
    schema_block = "\n".join(lines) if lines else "(nincs elérhető entitástípus ehhez a felhasználóhoz)"
    return (
        f"{_BASE_SYSTEM_PROMPT}\n\n"
        "Elérhető entitástípusok és mezőik (mező:típus) ennél a felhasználónál:\n"
        f"{schema_block}\n\n"
        "Ha egy select-jellegű szöveges mező pontos lehetséges értékeire van szükséged "
        "(pl. milyen 'allapot' értékek léteznek), hívd meg a describe_entity-t az adott "
        "entitástípusra."
    )


def ask(db: Session, employee: Employee, question: str) -> str:
    """A kérdés megválaszolása Gemini function-callinggal.

    A hurok kézzel megy (nem az SDK automatic function callingjával): minden
    egyes eszközhívásnál újra le kell futnia a jogosultság-ellenőrzésnek a
    KÉRDEZŐ nevében, és az eszközök a mi DB-sessionünkön dolgoznak - ezt az
    automatikus változat nem tudná átadni."""
    if not settings.gemini_api_key:
        return "Az AI Assistant nincs beállítva (hiányzik a GEMINI_API_KEY)."

    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=_build_system_prompt(db, employee),
        tools=[types.Tool(function_declarations=TOOLS)],
        # Az SDK alapból MAGA hívná meg a python függvényeket - itt nem ezt
        # akarjuk (lásd a docstringet), a hurkot mi vezetjük.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        max_output_tokens=2048,
    )
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=question)])]

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.models.generate_content(
                model=settings.gemini_model, contents=contents, config=config
            )
            hivasok = response.function_calls or []
            if not hivasok:
                return (response.text or "").strip() or "Nem érkezett válasz szöveg."

            # A modell saját fordulóját visszatesszük a beszélgetésbe, hogy a
            # következő körben lássa, mit kért.
            jelolt = response.candidates[0].content if response.candidates else None
            contents.append(jelolt or types.Content(role="model", parts=[]))

            valaszok = []
            for hivas in hivasok:
                try:
                    eredmeny = _execute_tool(db, employee, hivas.name or "", dict(hivas.args or {}))
                except ValueError as exc:
                    # Rossz paraméter (pl. értelmezhetetlen filters): a modell
                    # javítani tudja a következő körben, nem kell elhasalnia.
                    eredmeny = {"error": str(exc)}
                valaszok.append(
                    types.Part.from_function_response(name=hivas.name or "", response=eredmeny)
                )
            contents.append(types.Content(role="user", parts=valaszok))
    except genai_errors.ClientError as exc:
        # 401/403: rossz kulcs; 429: rate limit - a felhasználónak más a teendő.
        if exc.code == 429:
            return "Az AI Assistant túlterhelt (rate limit) - próbáld újra kicsit később."
        if exc.code in (401, 403):
            return "Az AI Assistant hitelesítési hibába ütközött (érvénytelen GEMINI_API_KEY)."
        return f"Az AI Assistant nem érhető el (API hiba): {exc}"
    except genai_errors.APIError as exc:
        return f"Az AI Assistant nem érhető el (hálózati/API hiba): {exc}"

    return "Nem sikerült választ generálni (túl sok lépés)."
