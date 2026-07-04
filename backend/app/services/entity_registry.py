"""Entity_type string -> SQLAlchemy modell megfeleltetés, a mező-láthatóság
Beállítások oldalának mezőtípus-lekérdezéséhez (lásd routes/field_visibility.py
"schema" végpontja) - null értékű boolean/date mezőknél a frontend a nyers
JSON értékből (null) nem tudja eldönteni, hogy checkbox vagy dátum-inputot
kell-e megjelenítenie, ezért a backend a tényleges oszloptípusból adja meg."""

from datetime import date, datetime
from decimal import Decimal

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


def get_field_types(entity_type: str) -> dict[str, str]:
    """{mezőnév: "boolean"|"date"|"datetime"|"number"|"text"} egy entitástípushoz."""
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return {}
    result: dict[str, str] = {}
    for name, column in model.__table__.columns.items():
        py_type = getattr(column.type, "python_type", None)
        if py_type is bool:
            result[name] = "boolean"
        elif py_type is date:
            result[name] = "date"
        elif py_type is datetime:
            result[name] = "datetime"
        elif py_type in (int, float, Decimal):
            result[name] = "number"
        else:
            result[name] = "text"
    return result
