from datetime import datetime

from pydantic import BaseModel


class FloraFeladatBase(BaseModel):
    megnevezes: str
    allapot: str | None = None
    cimke: str | None = None
    hatarido: datetime | None = None
    kesz_anyag_linkje: str | None = None
    leiras: str | None = None
    letrehozas_idopontja: datetime | None = None
    felelos_id: int | None = None
    felvezette_id: int | None = None


class FloraFeladatCreate(FloraFeladatBase):
    pass


class FloraFeladatUpdate(BaseModel):
    # A megnevezés és a leírás is átírható (a felhasználó kérése) - korábban
    # hiányoztak innen, ezért a lista "Megnevezés" cellájának szerkesztése
    # csendben elveszett (a séma eldobta az ismeretlen mezőt).
    megnevezes: str | None = None
    allapot: str | None = None
    cimke: str | None = None
    hatarido: datetime | None = None
    felelos_id: int | None = None
    leiras: str | None = None
    kesz_anyag_linkje: str | None = None


class FloraFeladatRead(FloraFeladatBase):
    id: int

    model_config = {"from_attributes": True}
