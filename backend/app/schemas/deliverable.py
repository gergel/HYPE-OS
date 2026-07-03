from datetime import date

from pydantic import BaseModel


class DeliverableBase(BaseModel):
    projekt_neve: str
    project_code_id: int | None = None
    project_id: int | None = None
    vago_employee_id: int | None = None
    campaign_id: int | None = None
    allapot: str | None = None
    hatarido: date | None = None
    koltseg: float | None = None
    kesz_anyag_url: str | None = None
    nyersanyag_url: str | None = None
    anyag_kikuldve: bool = False


class DeliverableCreate(DeliverableBase):
    pass


class DeliverableUpdate(BaseModel):
    allapot: str | None = None
    vago_employee_id: int | None = None
    kesz_anyag_url: str | None = None
    anyag_kikuldve: bool | None = None


class DeliverableRead(DeliverableBase):
    id: int
    extra: dict | None = None

    model_config = {"from_attributes": True}
