from datetime import date, datetime

from pydantic import BaseModel

from app.models.contract import ContractType

JsonScalar = dict | list | float | str | bool | None


class ContractBase(BaseModel):
    tipus: ContractType
    client_id: int | None = None
    employee_id: int | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    szerzodes_allapota: str | None = None
    keltezes: date | None = None
    alairva: bool = False


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    szerzodes_allapota: str | None = None
    alairva: bool | None = None
    szerzodes_file_url: str | None = None


class ContractRead(ContractBase):
    id: int
    szerzodes_file_url: str | None = None

    # a 'Keretszerződés' / 'Alvállakozó keretszerződés' Notion táblák maradék mezői
    letrehozta_notion: JsonScalar = None
    vallalkozas_kepviseloje: str | None = None
    created_at_notion: datetime | None = None
    keretszerzodes_kuld: bool | None = None
    email: str | None = None
    szemely_notion_ids: JsonScalar = None
    nev: str | None = None
    kulsos_notion_ids: JsonScalar = None
    vallalkozas_nyilvantartasi_szam: str | None = None
    szerzodes_megjegyzes: str | None = None

    model_config = {"from_attributes": True}
