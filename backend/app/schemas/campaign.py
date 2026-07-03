from datetime import date

from pydantic import BaseModel


class CampaignBase(BaseModel):
    nev: str
    kampany_statusza: str | None = None
    hatarido: date | None = None
    intervalluma: str | None = None
    kesz: bool = False
    felelos_employee_id: int | None = None
    client_id: int | None = None


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    kampany_statusza: str | None = None
    hatarido: date | None = None
    kesz: bool | None = None


class CampaignRead(CampaignBase):
    id: int
    extra: dict | None = None

    model_config = {"from_attributes": True}
