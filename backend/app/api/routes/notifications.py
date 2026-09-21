from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee
from app.schemas.notification import NotificationRead, UnreadCount
from app.services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_my_notifications(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    return notifications.list_for_employee(db, current_user.id)


@router.get("/unread-count", response_model=UnreadCount)
def get_unread_count(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    return UnreadCount(count=notifications.unread_count(db, current_user.id))


@router.post("/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    notifications.mark_read(db, current_user.id, notification_id)


@router.post("/read-all", status_code=204)
def mark_all_read(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    notifications.mark_all_read(db, current_user.id)


# Device ownership is derived from the authenticated user, never client-supplied.
from datetime import datetime, timezone
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from app.core.security import decode_access_token, oauth2_scheme
from app.models.push import PushDevice
from app.services.apple_push import PushConfig


class DeviceToken(BaseModel):
    token: str = Field(pattern=r"^[0-9a-f]{32,512}$")


class DeviceRegistration(DeviceToken):
    environment: Literal["sandbox", "production"]


@router.put("/devices")
def register_device(payload: DeviceRegistration, db: Session = Depends(get_db),
                    current_user: Employee = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    if current_user.is_active is False:
        raise HTTPException(status_code=403, detail="Inaktív fiók")
    expires = datetime.fromtimestamp(decode_access_token(token)["exp"], timezone.utc)
    now = datetime.now(timezone.utc)
    values = dict(employee_id=current_user.id, token=payload.token, environment=payload.environment,
                  expires_at=expires, registered_at=now)
    stmt = insert(PushDevice).values(**values)
    db.execute(stmt.on_conflict_do_update(constraint="uq_push_token_environment", set_=values))
    db.commit()
    return {"enabled": PushConfig.load().enabled}


@router.delete("/devices", status_code=204)
def unregister_device(payload: DeviceToken, db: Session = Depends(get_db),
                      current_user: Employee = Depends(get_current_user)):
    db.execute(delete(PushDevice).where(PushDevice.employee_id == current_user.id, PushDevice.token == payload.token))
    db.commit()


from pydantic import ConfigDict, StrictBool
from app.models.push import NotificationPreference
from app.services.notification_preferences import KINDS, enabled


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: dict[str, StrictBool]


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    return {"preferences": {kind: enabled(db, current_user.id, kind) for kind in KINDS}}


@router.put("/preferences")
def save_preferences(payload: PreferenceUpdate, db: Session = Depends(get_db),
                     current_user: Employee = Depends(get_current_user)):
    if set(payload.preferences) - KINDS.keys():
        raise HTTPException(status_code=422, detail="Ismeretlen értesítési típus")
    # Partial updates avoid overwriting unrelated settings from another device.
    for kind, value in payload.preferences.items():
        stmt = insert(NotificationPreference).values(employee_id=current_user.id, kind=kind, enabled=value)
        db.execute(stmt.on_conflict_do_update(index_elements=["employee_id", "kind"], set_={"enabled": value}))
    db.commit()
    return get_preferences(db, current_user)
