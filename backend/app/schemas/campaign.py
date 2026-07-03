from datetime import date

from pydantic import BaseModel

JsonScalar = dict | list | float | str | bool | None


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

    # a 'Kampányok' Notion tábla maradék mezői
    forgatas_utomunka: str | None = None
    forgatas: bool | None = None
    kreativ_team_database_notion_ids: JsonScalar = None
    van_utomunka: bool | None = None
    kampany_felelose_notion_ids: JsonScalar = None
    leiras: str | None = None
    utomunka_szoveg: str | None = None
    forgatasok_notion_ids: JsonScalar = None

    model_config = {"from_attributes": True}
