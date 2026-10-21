from datetime import date, datetime

from pydantic import BaseModel


class HypeTodoBase(BaseModel):
    feladat: str
    allapot: str | None = None
    leiras: str | None = None
    kategoria: str | None = None
    hatarido: date | None = None
    csatolando_link: str | None = None
    letrehozas_idopontja: datetime | None = None
    aki_felvezette_id: int | None = None
    ellenorzes_felelos_id: int | None = None
    aki_ellenorizte_id: int | None = None


class HypeTodoCreate(HypeTodoBase):
    felelos_employee_ids: list[int] = []


class HypeTodoUpdate(BaseModel):
    allapot: str | None = None
    hatarido: date | None = None
    felelos_employee_ids: list[int] | None = None


class HypeTodoRead(HypeTodoBase):
    id: int
    felelos_employee_ids: list[int] = []

    model_config = {"from_attributes": True}
