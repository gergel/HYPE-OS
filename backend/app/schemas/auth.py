from pydantic import BaseModel

from app.models.employee import SystemRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str | None
    role: SystemRole

    model_config = {"from_attributes": True}
