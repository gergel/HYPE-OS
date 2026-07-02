from datetime import date

from pydantic import BaseModel


class CallsheetBase(BaseModel):
    project_id: int
    employee_id: int | None = None
    diszpo_pdf_url: str | None = None
    reszvevok: str | None = None
    tulora: float | None = None
    datum: date | None = None
    statusz: str | None = None
    gmail_thread_id: str | None = None


class CallsheetCreate(CallsheetBase):
    pass


class CallsheetUpdate(BaseModel):
    statusz: str | None = None
    diszpo_pdf_url: str | None = None
    gmail_thread_id: str | None = None


class CallsheetRead(CallsheetBase):
    id: int

    model_config = {"from_attributes": True}
