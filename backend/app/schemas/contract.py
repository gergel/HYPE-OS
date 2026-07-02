from datetime import date

from pydantic import BaseModel

from app.models.contract import ContractType


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

    model_config = {"from_attributes": True}
