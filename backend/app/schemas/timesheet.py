from datetime import datetime

from pydantic import BaseModel

JsonScalar = dict | list | float | str | bool | None


class TimesheetBase(BaseModel):
    employee_id: int
    deliverable_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    koltseg: float | None = None
    statusz: str | None = None
    completed: bool = False


class TimesheetCreate(TimesheetBase):
    pass


class TimesheetUpdate(BaseModel):
    end_date: datetime | None = None
    statusz: str | None = None
    completed: bool | None = None


class TimesheetRead(TimesheetBase):
    id: int
    idotartam_perc: int | None = None

    # a munkaidő-elszámoló táblák maradék mezői (lásd scripts/dump_extra_keys.py)
    person_notion: JsonScalar = None
    fut: bool | None = None
    orabere: float | None = None
    timesheet_status: str | None = None
    nev: str | None = None
    time_xp: str | None = None
    time_szoveg: str | None = None
    time_minutes: float | None = None
    xp_pontozas: float | None = None
    vagok_notion_ids: JsonScalar = None
    mai_percek: float | None = None
    percek_2025_majus: float | None = None
    mai_xp: float | None = None
    kezdes_ma: bool | None = None
    akkori_orabere: float | None = None
    timesheet_public_notion_ids: JsonScalar = None
    percek_lista: JsonScalar = None

    model_config = {"from_attributes": True}
