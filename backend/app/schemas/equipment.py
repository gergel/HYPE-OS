from datetime import date, datetime

from pydantic import BaseModel

from app.models.equipment import TrackMode

JsonScalar = dict | list | float | str | bool | None


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
    project_ids: list[int] = []

    # a 'Leltár' Notion tábla maradék mezői, egyenként (lásd scripts/dump_extra_keys.py)
    leltar_20240415: bool | None = None
    leltar_20250104: bool | None = None
    hasznalhato: str | None = None
    leltar_20240526: bool | None = None
    rendszerbe_kerules_idopontja: datetime | None = None
    letrehozta_notion: JsonScalar = None
    leltar_20240620: bool | None = None
    hany_napot_dolgozott: float | None = None
    status_notion: str | None = None
    hany_forgatason_vett_reszt: str | None = None
    mai_notion: bool | None = None
    leltar_20250519: bool | None = None
    qr_kod: str | None = None
    created_at_notion: datetime | None = None
    leltar_tetelek_notion_ids: JsonScalar = None
    forgatasi_napok: str | None = None
    projektek_notion_ids: JsonScalar = None
    qr: str | None = None
    eszkozkiviteli_ki_notion_ids: JsonScalar = None
    eszkozkiviteli_vissza_notion_ids: JsonScalar = None
    megjegyzes: str | None = None
    stock_qty: float | None = None
    zoom_atfogas: JsonScalar = None
    stock_igenyek_notion_ids: JsonScalar = None
    jovobeni: str | None = None
    megeri_e_szerelni: str | None = None
    szerviz_leiras: str | None = None
    selejtezes_elhagyas_datuma: date | None = None
    ahol_utoljara_volt: str | None = None

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
