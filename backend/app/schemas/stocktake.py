from datetime import datetime

from pydantic import BaseModel


class StocktakeItemRead(BaseModel):
    id: int
    equipment_id: int
    equipment_nev: str
    kategoria: str | None
    track_mode: str
    expected_qty: int | None
    counted_qty: int | None
    status: str | None

    model_config = {"from_attributes": True}


class StocktakeItemUpdate(BaseModel):
    status: str | None = None
    counted_qty: int | None = None


class StocktakeSessionRead(BaseModel):
    id: int
    started_by_employee_id: int
    started_by_name: str
    created_at: datetime
    completed_at: datetime | None
    items: list[StocktakeItemRead]

    model_config = {"from_attributes": True}


class StocktakeSessionListItem(BaseModel):
    id: int
    started_by_name: str
    created_at: datetime
    completed_at: datetime | None
    item_count: int


class StocktakeStatusGroupItem(BaseModel):
    equipment_id: int
    nev: str


class StocktakeStatusGroup(BaseModel):
    status: str
    items: list[StocktakeStatusGroupItem]


class StocktakeMissingStock(BaseModel):
    equipment_id: int
    nev: str
    expected_qty: int
    counted_qty: int
    hiany: int


class StocktakeSummary(BaseModel):
    problemas_statuszok: list[StocktakeStatusGroup]
    hianyzo_keszletek: list[StocktakeMissingStock]
