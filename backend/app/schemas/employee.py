from datetime import date

from pydantic import BaseModel

from app.models.employee import EmployeeType, SystemRole


class EmployeeBase(BaseModel):
    full_name: str
    tipus: EmployeeType
    email: str | None = None
    telefon: str | None = None
    jogositvany: str | None = None
    elso_munkanap: date | None = None
    utolso_munkanap: date | None = None


class EmployeeCreate(EmployeeBase):
    role: SystemRole = SystemRole.OPERATOR
    password: str


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    tipus: EmployeeType | None = None
    email: str | None = None
    telefon: str | None = None
    jogositvany: str | None = None
    is_active: bool | None = None


class EmployeeRead(EmployeeBase):
    id: int
    role: SystemRole
    is_active: bool

    model_config = {"from_attributes": True}


class RateBase(BaseModel):
    orabler: float | None = None
    napibler: float | None = None
    tulora: float | None = None
    plusz_nap: float | None = None
    havi_alap: float | None = None
    elso_munkanap: date | None = None
    utolso_munkanap: date | None = None


class RateCreate(RateBase):
    employee_id: int


class RateUpdate(RateBase):
    pass


class RateRead(RateBase):
    id: int
    employee_id: int

    model_config = {"from_attributes": True}
