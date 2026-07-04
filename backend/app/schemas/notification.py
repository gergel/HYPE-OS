from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    kind: str
    message: str
    link: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCount(BaseModel):
    count: int
