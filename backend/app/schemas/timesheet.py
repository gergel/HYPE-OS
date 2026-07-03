from datetime import datetime

from pydantic import BaseModel


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
    extra: dict | None = None

    model_config = {"from_attributes": True}
