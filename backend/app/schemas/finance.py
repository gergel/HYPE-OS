from datetime import date

from pydantic import BaseModel


class ExpenseBase(BaseModel):
    megnevezes: str
    project_code_id: int | None = None
    employee_id: int | None = None
    tipus: str | None = None
    netto: float | None = None
    brutto: float | None = None
    penznem: str = "HUF"
    kifizetes_modja: str | None = None
    fizetes_hatarideje: date | None = None
    kesz: bool = False


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    kesz: bool | None = None
    kifizetes_modja: str | None = None
    fizetes_hatarideje: date | None = None


class ExpenseRead(ExpenseBase):
    id: int

    model_config = {"from_attributes": True}


class RevenueBase(BaseModel):
    project_code_id: int
    bevetel_formaja: str | None = None
    netto: float | None = None
    brutto: float | None = None
    penznem: str = "HUF"
    fizetes_hatarideje: date | None = None
    fizetes_datuma: date | None = None


class RevenueCreate(RevenueBase):
    pass


class RevenueUpdate(BaseModel):
    fizetes_datuma: date | None = None


class RevenueRead(RevenueBase):
    id: int

    model_config = {"from_attributes": True}


class KpForgalomBase(BaseModel):
    expense_id: int | None = None
    forgalom: str | None = None
    osszeg: float | None = None
    penznem: str = "HUF"
    legalis: str | None = None
    kiadas_datuma: date | None = None


class KpForgalomCreate(KpForgalomBase):
    pass


class KpForgalomUpdate(KpForgalomBase):
    pass


class KpForgalomRead(KpForgalomBase):
    id: int

    model_config = {"from_attributes": True}
