from datetime import date

from pydantic import BaseModel

from app.models.equipment import TrackMode


class EquipmentBase(BaseModel):
    nev: str
    serial_number: str | None = None
    kategoria: str | None = None
    allapot: str | None = None
    archive_statusz: str | None = None
    track_mode: TrackMode = TrackMode.ASSET
    osszes_mennyiseg: int | None = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    nev: str | None = None
    kategoria: str | None = None
    allapot: str | None = None
    archive_statusz: str | None = None
    osszes_mennyiseg: int | None = None


class EquipmentRead(EquipmentBase):
    id: int
    extra: dict | None = None

    model_config = {"from_attributes": True}


class AssignmentBase(BaseModel):
    equipment_id: int
    project_id: int
    qty: int = 1
    aki_kivitte: str | None = None
    kivitel_datuma: date | None = None
    aki_visszahozta: str | None = None
    visszahozatal_datuma: date | None = None


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    aki_visszahozta: str | None = None
    visszahozatal_datuma: date | None = None


class AssignmentRead(AssignmentBase):
    id: int
    extra: dict | None = None

    model_config = {"from_attributes": True}
