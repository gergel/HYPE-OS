from datetime import date, datetime

from pydantic import BaseModel

JsonScalar = dict | list | float | str | bool | None


class TaskBase(BaseModel):
    feladat: str
    allapot: str | None = None
    hatarido: date | None = None
    kategoria: str | None = None
    checked: bool = False
    leiras: str | None = None


class TaskCreate(TaskBase):
    felelos_employee_ids: list[int] = []


class TaskUpdate(BaseModel):
    allapot: str | None = None
    checked: bool | None = None
    hatarido: date | None = None
    felelos_employee_ids: list[int] | None = None


class TaskRead(TaskBase):
    id: int
    #: Melyik projekthez tartozik (az automatikus papírozás-feladatoknál van
    #: kitöltve, lásd services/papirozas_feladatok.py).
    project_id: int | None = None

    # a TEENDŐK/Ági to do list/HYPE TO-DO LIST/Archive feladatok táblák maradék mezői
    aki_felvezette_notion: JsonScalar = None
    letrehozas_idopontja: datetime | None = None
    felelos_notion: JsonScalar = None
    ugyfel: str | None = None
    ellenorzes_felelos_notion: JsonScalar = None
    aki_ellenorizte_keszbe_rakta_notion: JsonScalar = None
    kovetkezo_lepes: str | None = None
    csatolni_valo_urls: JsonScalar = None
    files_media_urls: JsonScalar = None

    model_config = {"from_attributes": True}
