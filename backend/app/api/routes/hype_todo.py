from app.api.crud_router import build_crud_router
from app.models.employee import Employee
from app.models.hype_todo import HypeTodoItem
from app.schemas.hype_todo import HypeTodoCreate, HypeTodoRead, HypeTodoUpdate

router = build_crud_router(
    model=HypeTodoItem,
    create_schema=HypeTodoCreate,
    update_schema=HypeTodoUpdate,
    read_schema=HypeTodoRead,
    prefix="/hype-todo",
    tags=["hype-todo"],
    page="/hype-todo-lista",
    m2m_fields={"felelos_employee_ids": ("felelosok", Employee)},
    entity_type="hypeTodo",
)
