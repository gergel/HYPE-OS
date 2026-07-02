from pydantic import BaseModel


class TimelineEventBase(BaseModel):
    entity_type: str
    entity_id: int
    event_type: str
    payload: dict | None = None


class TimelineEventCreate(TimelineEventBase):
    pass


class TimelineEventRead(TimelineEventBase):
    id: int

    model_config = {"from_attributes": True}
