from datetime import date

from pydantic import BaseModel


class ProjectCodeBase(BaseModel):
    projektkod: str
    client_id: int
    contract_id: int | None = None
    datum: date | None = None
    esemeny_allapota: str | None = None
    penznem: str = "HUF"
    arfolyam: float | None = None
    tig_statusza: str | None = None
    szamla_statusza: str | None = None


class ProjectCodeCreate(ProjectCodeBase):
    pass


class ProjectCodeUpdate(BaseModel):
    esemeny_allapota: str | None = None
    contract_id: int | None = None
    tig_statusza: str | None = None
    szamla_statusza: str | None = None


class ProjectCodeRead(ProjectCodeBase):
    id: int
    osszes_koltseg: float
    becsult_profit: float

    model_config = {"from_attributes": True}
