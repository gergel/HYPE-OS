from datetime import date

from pydantic import BaseModel


class TaskBase(BaseModel):
    feladat: str
    allapot: str | None = None
    hatarido: date | None = None
    kategoria: str | None = None
    checked: bool = False


class TaskCreate(TaskBase):
    felelos_employee_ids: list[int] = []


class TaskUpdate(BaseModel):
    allapot: str | None = None
    checked: bool | None = None
    hatarido: date | None = None
    felelos_employee_ids: list[int] | None = None


class TaskRead(TaskBase):
    id: int

    model_config = {"from_attributes": True}
