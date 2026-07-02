from pydantic import BaseModel


class FeedbackBase(BaseModel):
    deliverable_id: int
    project_id: int | None = None
    forgatta_employee_id: int | None = None
    technikai_helyesseg: float | None = None
    kreativ_kepivilag: float | None = None
    nyersanyag_felhasznalhatosaga: float | None = None
    ertekeles_kuldese: str | None = None
    visszajelzes_szoveg: str | None = None


class FeedbackCreate(FeedbackBase):
    pass


class FeedbackUpdate(BaseModel):
    ertekeles_kuldese: str | None = None
    visszajelzes_szoveg: str | None = None


class FeedbackRead(FeedbackBase):
    id: int
    atlag: float | None = None

    model_config = {"from_attributes": True}
