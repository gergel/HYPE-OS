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
    megjegyzes: str | None

    model_config = {"from_attributes": True}


class StocktakeItemUpdate(BaseModel):
    status: str | None = None
    counted_qty: int | None = None
    #: Magyarázat a nem "Jó" állapothoz - üres szöveg törli.
    megjegyzes: str | None = None


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
    #: A leltározó magyarázata (miért szerelendő / miért van szervizben).
    megjegyzes: str | None = None
    #: Ehhez az állapothoz kötelező a magyarázat (lásd services/stocktake.py
    #: MAGYARAZATOT_IGENYLO_STATUSZOK) - a felület ebből tudja, hol kell
    #: hiányként kiabálnia.
    magyarazat_kell: bool = False


class StocktakeStatusGroup(BaseModel):
    status: str
    items: list[StocktakeStatusGroupItem]


class StocktakeMissingStock(BaseModel):
    equipment_id: int
    nev: str
    expected_qty: int
    counted_qty: int
    hiany: int


class StocktakeSurplusStock(BaseModel):
    """Amiből TÖBB van, mint az elvárt darabszám - ez is eltérés, nem öröm."""

    equipment_id: int
    nev: str
    expected_qty: int
    counted_qty: int
    tobblet: int


class StocktakeSummary(BaseModel):
    problemas_statuszok: list[StocktakeStatusGroup]
    hianyzo_keszletek: list[StocktakeMissingStock]
    tobblet_keszletek: list[StocktakeSurplusStock] = []
    #: Amihez még hiányzik a kötelező magyarázat - amíg van ilyen, a leltár
    #: nem zárható le (lásd services/stocktake.complete_session).
    magyarazatra_var: list[StocktakeStatusGroupItem] = []
