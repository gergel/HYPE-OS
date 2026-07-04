from pydantic import BaseModel


class FieldVisibilityRead(BaseModel):
    entity_type: str
    visible_fields: list[str] | None = None

    model_config = {"from_attributes": True}


class FieldVisibilityUpdate(BaseModel):
    visible_fields: list[str] | None = None
