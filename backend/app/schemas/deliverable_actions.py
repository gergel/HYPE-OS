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


class TimerState(BaseModel):
    my_running_since: datetime | None
    by_employee: list[TimerEmployeeSummary]
    total_minutes: float
    total_cost: float | None = None
