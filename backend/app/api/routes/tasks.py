from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.models.employee import Employee
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services import notifications


def _after_task_update(obj: Task, data: dict, m2m_changes: dict, db: Session, current_user: Employee) -> None:
    """Ha a PATCH új felelőst adott a feladathoz, azt értesíti - lásd feladatok oldal."""
    added = m2m_changes.get("felelosok", {}).get("added", set())
    if not added:
        return
    for employee_id in added:
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="assignment",
            message=f"{current_user.full_name} rád osztott egy feladatot: {obj.feladat}",
            link=f"/feladatok/{obj.id}",
            actor_id=current_user.id,
        )
    db.commit()


def _after_task_create(obj, data, db, current_user):
    _after_task_update(obj, data, {"felelosok": {"added": {person.id for person in obj.felelosok}}}, db, current_user)


router = build_crud_router(
    model=Task,
    create_schema=TaskCreate,
    update_schema=TaskUpdate,
    read_schema=TaskRead,
    prefix="/tasks",
    tags=["tasks"],
    page="/feladatok",
    m2m_fields={"felelos_employee_ids": ("felelosok", Employee)},
    after_update=_after_task_update,
    after_create=_after_task_create,
    entity_type="task",
)
