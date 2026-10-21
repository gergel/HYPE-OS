"""Az árajánlat-készítő API bemenetei (lásd api/routes/quotes.py). A pénz
egész forint; az alkalom / mennyiség tört is lehet."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class KategoriaIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int | None = None


class KategoriaPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


class KatalogusTetelIn(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=255)
    default_description: str | None = None
    unit: str = "db"
    base_price: int = Field(ge=0)
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    price_median: int | None = Field(default=None, ge=0)
    is_active: bool = True
    sort_order: int | None = None
    tags: list[str] = []


class KatalogusTetelPatch(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    default_description: str | None = None
    unit: str | None = None
    base_price: int | None = Field(default=None, ge=0)
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    price_median: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = None
    tags: list[str] | None = None


class SablonIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    brand: str = "HYPE"
    pricing_mode: str = "one_off"
    summary_label: str | None = None
    occasions_label: str | None = None
    typical_total: int | None = Field(default=None, ge=0)
    default_note_id: int | None = None
    sort_order: int | None = None
    is_active: bool = True


class SablonPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    brand: str | None = None
    pricing_mode: str | None = None
    summary_label: str | None = None
    occasions_label: str | None = None
    typical_total: int | None = Field(default=None, ge=0)
    default_note_id: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class SablonSorIn(BaseModel):
    catalog_item_id: int | None = None
    section: str | None = None
    name_override: str | None = None
    description_override: str | None = None
    unit_override: str | None = None
    default_occasions: float = Field(default=1, ge=0)
    default_quantity: float = Field(default=1, ge=0)
    price_override: int | None = Field(default=None, ge=0)
    is_optional: bool = False


class SablonSorPatch(BaseModel):
    catalog_item_id: int | None = None
    section: str | None = None
    name_override: str | None = None
    description_override: str | None = None
    unit_override: str | None = None
    default_occasions: float | None = Field(default=None, ge=0)
    default_quantity: float | None = Field(default=None, ge=0)
    price_override: int | None = Field(default=None, ge=0)
    is_optional: bool | None = None


class SablonAjanlatbolIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class MegjegyzesIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1)
    sort_order: int | None = None


class MegjegyzesPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, min_length=1)
    sort_order: int | None = None


class UgyfelIn(BaseModel):
    nev: str = Field(min_length=1, max_length=255)
    adoszam: str | None = None
    szekhely: str | None = None


class AjanlatIn(BaseModel):
    template_id: int | None = None
    brand: str | None = None
    client_id: int | None = None
    project_name: str = ""
    event_date_from: date | None = None
    event_date_to: date | None = None
    location: str | None = None
    pricing_mode: str | None = None
    months: int | None = Field(default=None, ge=1, le=120)
    note_text: str | None = None


class AjanlatPatch(BaseModel):
    brand: str | None = None
    client_id: int | None = None
    project_name: str | None = None
    event_date_from: date | None = None
    event_date_to: date | None = None
    location: str | None = None
    status: str | None = None
    pricing_mode: str | None = None
    months: int | None = Field(default=None, ge=1, le=120)
    discount_percent: float | None = Field(default=None, ge=0, le=100)
    discount_amount: int | None = Field(default=None, ge=0)
    vat_percent: float | None = Field(default=None, ge=0, le=100)
    summary_label: str | None = None
    occasions_label: str | None = None
    note_text: str | None = None
    internal_note: str | None = None


class SorIn(BaseModel):
    section: str | None = None
    name: str = ""
    description: str | None = None
    occasions: float = Field(default=1, ge=0)
    quantity: float = Field(default=1, ge=0)
    unit: str | None = None
    unit_price: int = Field(default=0, ge=0)
    line_discount_percent: float = Field(default=0, ge=0, le=100)
    is_optional: bool = False
    after_item_id: int | None = None


class SorPatch(BaseModel):
    catalog_item_id: int | None = None
    section: str | None = None
    name: str | None = None
    description: str | None = None
    occasions: float | None = Field(default=None, ge=0)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    unit_price: int | None = Field(default=None, ge=0)
    line_discount_percent: float | None = Field(default=None, ge=0, le=100)
    is_optional: bool | None = None


class KatalogusbolIn(BaseModel):
    catalog_item_id: int
    section: str | None = None


class SorrendElem(BaseModel):
    id: int
    section: str | None = None


class SorrendIn(BaseModel):
    items: list[SorrendElem]


class ArFrissitesIn(BaseModel):
    #: None: minden katalógusból jött sor.
    item_ids: list[int] | None = None
