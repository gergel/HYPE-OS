from datetime import datetime

from pydantic import BaseModel


class PostShootFeedbackRead(BaseModel):
    id: int
    project_id: int
    erdemleges_tortent: str | None = None
    technika_info: str | None = None
    egyeb: str | None = None
    werk_fotok: list[dict] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
