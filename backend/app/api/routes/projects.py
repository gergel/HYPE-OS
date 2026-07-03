from app.api.crud_router import build_crud_router
from app.models.employee import Employee
from app.models.equipment import Equipment
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = build_crud_router(
    model=Project,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    read_schema=ProjectRead,
    prefix="/projects",
    tags=["projects"],
    m2m_fields={"crew_employee_ids": ("crew", Employee), "equipment_ids": ("equipment", Equipment)},
)
