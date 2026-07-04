"""Entity_type string -> SQLAlchemy modell megfeleltetés, a mező-láthatóság
Beállítások oldalának mezőtípus-lekérdezéséhez (lásd routes/field_visibility.py
"schema" végpontja) - null értékű boolean/date mezőknél a frontend a nyers
JSON értékből (null) nem tudja eldönteni, hogy checkbox vagy dátum-inputot
kell-e megjelenítenie, ezért a backend a tényleges oszloptípusból adja meg.

Két módon ismerjük fel a Notion "select" mezőket:
1. Valódi DB enum oszlopok (pl. Employee.tipus/role) - ezeknél a teljes
   definiált értékkészletet adjuk vissza (nem csak az aktuálisan használt
   értékeket), ez mindig megbízható.
2. Szöveges oszlopok, amiknek kevés, rövid, ismétlődő értéke van a táblában
   (lásd _select_options) - ez egy tényleges adaton alapuló heurisztika, mert
   az eredeti Notion property-típusokat és színeket nem tároltuk el
   importáláskor. Az azonosító-jellegű mezőket (név, email, URL stb.) explicit
   kizárjuk, mert ezeknél a véletlen adatismétlődés (pl. több "No Email Ember"
   nevű Notion-import placeholder) hamis select-találatot adna."""

from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import Enum as SAEnum
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.client import Client
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.equipment import Equipment
from app.models.finance import Expense, Revenue
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.task import Task

ENTITY_MODELS: dict[str, type] = {
    "project": Project,
    "client": Client,
    "projectCode": ProjectCode,
    "employee": Employee,
    "equipment": Equipment,
    "campaign": Campaign,
    "task": Task,
    "expense": Expense,
    "revenue": Revenue,
    "deliverable": Deliverable,
}

SELECT_LIKE_MAX_DISTINCT = 20
SELECT_LIKE_MAX_VALUE_LENGTH = 60

# Azonosító-jellegű/szabad szöveges mezők - ezeket sosem tekintjük select-nek,
# még akkor sem, ha a jelenlegi adatban véletlenül kevés/ismétlődő értékük van.
NOT_SELECT_NAME_PATTERN_FRAGMENTS = (
    "nev",
    "name",
    "email",
    "telefon",
    "phone",
    "cim",
    "url",
    "leiras",
    "description",
    "jegyzet",
    "megjegyzes",
    "comment",
    "szoveg",
    "text",
    "brief",
    "notion_ids",
    "serial",
    "szam",
    "code",
    "kod",
)


class FieldTypeInfo(TypedDict, total=False):
    type: str
    options: list[str]


def _select_options(name: str, db: Session, column) -> list[str] | None:
    """Ha egy szöveges oszlopnak kevés (<= SELECT_LIKE_MAX_DISTINCT), rövid és
    ismétlődő értéke van a táblában, azt Notion select-mezőnek tekintjük, és
    visszaadjuk a lehetséges értékeket (legördülő listához, lásd
    EditableDetailGrid) - máskülönben None (valószínűleg szabad szöveg)."""
    lowered = name.lower()
    if any(fragment in lowered for fragment in NOT_SELECT_NAME_PATTERN_FRAGMENTS):
        return None
    rows = db.execute(
        select(column, func.count()).where(column.is_not(None)).group_by(column).order_by(func.count().desc())
    ).all()
    if not rows or len(rows) > SELECT_LIKE_MAX_DISTINCT:
        return None
    if not any(count > 1 for _, count in rows):
        return None
    values = [value for value, _ in rows]
    if any(len(v) > SELECT_LIKE_MAX_VALUE_LENGTH or "\n" in v for v in values):
        return None
    return values


def get_field_types(entity_type: str, db: Session | None = None) -> dict[str, FieldTypeInfo]:
    """{mezőnév: {"type": "boolean"|"date"|"datetime"|"number"|"select"|"text", "options"?: [...]}}
    egy entitástípushoz. Az "options" csak "select" típusnál van jelen. db
    hiányában a szöveges mezők mindig sima "text"-ként jönnek vissza (nincs
    select-detektálás adat nélkül)."""
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return {}
    result: dict[str, FieldTypeInfo] = {}
    for name, column in model.__table__.columns.items():
        if isinstance(column.type, SAEnum):
            result[name] = {"type": "select", "options": list(column.type.enums)}
            continue
        py_type = getattr(column.type, "python_type", None)
        if py_type is bool:
            result[name] = {"type": "boolean"}
        elif py_type is date:
            result[name] = {"type": "date"}
        elif py_type is datetime:
            result[name] = {"type": "datetime"}
        elif py_type in (int, float, Decimal):
            result[name] = {"type": "number"}
        elif py_type is str and db is not None:
            options = _select_options(name, db, column)
            result[name] = {"type": "select", "options": options} if options else {"type": "text"}
        else:
            result[name] = {"type": "text"}
    return result
