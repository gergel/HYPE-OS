from pydantic import BaseModel


class PageAccessRead(BaseModel):
    employee_id: int
    allowed_pages: list[str] | None = None

    model_config = {"from_attributes": True}


class PageAccessUpdate(BaseModel):
    allowed_pages: list[str] | None = None


class MyAccess(BaseModel):
    allowed_pages: list[str] | None = None
