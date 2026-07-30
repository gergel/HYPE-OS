from datetime import datetime

from pydantic import BaseModel


class AssignableEmployee(BaseModel):
    id: int
    full_name: str


class VinyoOptions(BaseModel):
    options: list[str]


class ContactOption(BaseModel):
    id: int
    full_name: str
    email: str | None = None


class ContactIdsPayload(BaseModel):
    contact_ids: list[int]


class CommentCreate(BaseModel):
    body: str


class CommentRead(BaseModel):
    id: int
    deliverable_id: int
    employee_id: int
    employee_name: str
    body: str
    created_at: datetime


class TimerEmployeeSummary(BaseModel):
    employee_id: int
    full_name: str
    total_minutes: float
    total_cost: float | None = None


class TimerRunningEntry(BaseModel):
    """Épp FUTÓ időmérés - névvel, hogy a felületen ne csak egy csupasz óra
    ketyegjen, hanem az is látszódjon, kinél fut."""

    employee_id: int
    full_name: str
    since: datetime
    #: A mérés indításakor RÖGZÍTETT órabér (Timesheet.akkori_orabere) - ebből
    #: számolja a felület másodpercenként a még futó mérés költségét is, hogy ne
    #: csak leállítás után derüljön ki, mennyibe kerül. Ha a felhasználó nem
    #: láthatja a forintokat, üresen megy vissza.
    orabere: float | None = None


class TimerState(BaseModel):
    my_running_since: datetime | None
    running: list[TimerRunningEntry] = []
    by_employee: list[TimerEmployeeSummary]
    total_minutes: float
    total_cost: float | None = None
