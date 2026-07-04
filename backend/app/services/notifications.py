"""Értesítések: hozzászólásban taggelve lettél, kommenteltek egy hozzád
tartozó anyagon, vagy kaptál egy új kiosztást (Utómunka Assigned To, Feladat
felelős) - lásd api/routes/notifications.py és a hívási helyeket
(deliverable_actions.add_comment, routes/postproduction.py, routes/tasks.py)."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.notification import Notification


def create_notification(db: Session, *, employee_id: int, kind: str, message: str, link: str, actor_id: int | None = None) -> None:
    """Sosem értesíti önmagát a felhasználó (actor_id == employee_id esetén nem hoz létre semmit)."""
    if actor_id is not None and employee_id == actor_id:
        return
    db.add(Notification(employee_id=employee_id, kind=kind, message=message, link=link))


def extract_mentioned_employee_ids(body: str, db: Session) -> set[int]:
    """A komment szövegében szereplő "@Teljes Név" említések alapján megkeresi
    a taggelt munkatársak ID-jét (egyszerű substring-egyezés, lásd
    CommentsSection.tsx - mindig "@Teljes Név " formában szúrja be a taget)."""
    mentioned: set[int] = set()
    for employee in db.scalars(select(Employee)):
        if f"@{employee.full_name}" in body:
            mentioned.add(employee.id)
    return mentioned


def list_for_employee(db: Session, employee_id: int, limit: int = 30) -> list[Notification]:
    return db.scalars(
        select(Notification)
        .where(Notification.employee_id == employee_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()


def unread_count(db: Session, employee_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.employee_id == employee_id, Notification.is_read.is_(False))
        )
        or 0
    )


def mark_read(db: Session, employee_id: int, notification_id: int) -> None:
    notification = db.get(Notification, notification_id)
    if notification is not None and notification.employee_id == employee_id:
        notification.is_read = True
        db.commit()


def mark_all_read(db: Session, employee_id: int) -> None:
    db.execute(
        update(Notification)
        .where(Notification.employee_id == employee_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
