from datetime import datetime

from pydantic import BaseModel


class DocumentAttachmentRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    kategoria: str
    filename: str
    url: str
    content_type: str | None = None
    meret_bajt: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
