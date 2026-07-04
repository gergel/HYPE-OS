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
