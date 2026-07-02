from app.api.crud_router import build_crud_router
from app.models.employee import Employee
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

router = build_crud_router(
    model=Task,
    create_schema=TaskCreate,
    update_schema=TaskUpdate,
    read_schema=TaskRead,
    prefix="/tasks",
    tags=["tasks"],
    m2m_fields={"felelos_employee_ids": ("felelosok", Employee)},
)
