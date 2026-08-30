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
    allapot: str | None = None
    cimke: str | None = None
    hatarido: datetime | None = None
    felelos_id: int | None = None


class FloraFeladatRead(FloraFeladatBase):
    id: int

    model_config = {"from_attributes": True}
