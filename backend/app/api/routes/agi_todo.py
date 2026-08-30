from app.api.crud_router import build_crud_router
from app.models.agi_todo import AgiTodoItem
from app.schemas.agi_todo import AgiTodoCreate, AgiTodoRead, AgiTodoUpdate

router = build_crud_router(
    model=AgiTodoItem,
    create_schema=AgiTodoCreate,
    update_schema=AgiTodoUpdate,
    read_schema=AgiTodoRead,
    prefix="/agi-todo",
    tags=["agi-todo"],
    page="/agi",
    entity_type="agiTodo",
)
