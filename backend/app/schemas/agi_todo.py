from datetime import date

from pydantic import BaseModel


class AgiTodoBase(BaseModel):
    feladat: str
    allapot: str | None = None
    ugyfel: str | None = None
    hatarido: date | None = None
    leiras: str | None = None
    kovetkezo_lepes: str | None = None
    csatolt_link: str | None = None


class AgiTodoCreate(AgiTodoBase):
    pass


class AgiTodoUpdate(BaseModel):
    allapot: str | None = None
    hatarido: date | None = None


class AgiTodoRead(AgiTodoBase):
    id: int

    model_config = {"from_attributes": True}
