from datetime import date

from pydantic import BaseModel


class ProjectBase(BaseModel):
    nev: str
    project_code_id: int
    campaign_id: int | None = None
    forgatas_datuma: date | None = None
    helyszin: str | None = None
    allapot: str | None = None


class ProjectCreate(ProjectBase):
    crew_employee_ids: list[int] = []


class ProjectUpdate(BaseModel):
    nev: str | None = None
    campaign_id: int | None = None
    forgatas_datuma: date | None = None
    helyszin: str | None = None
    allapot: str | None = None
    crew_employee_ids: list[int] | None = None


class ProjectRead(ProjectBase):
    id: int
    extra: dict | None = None

    model_config = {"from_attributes": True}
