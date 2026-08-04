from sqlalchemy.orm import selectinload

from app.api.crud_router import build_crud_router
from app.models.project_code import ProjectCode
from app.schemas.project_code import ProjectCodeCreate, ProjectCodeRead, ProjectCodeUpdate

router = build_crud_router(
    model=ProjectCode,
    create_schema=ProjectCodeCreate,
    update_schema=ProjectCodeUpdate,
    read_schema=ProjectCodeRead,
    prefix="/project-codes",
    tags=["project-codes"],
    # Külön jogosultsági hatókör, NEM ugyanaz, mint a Projekteké (lásd
    # projects.py page="/projektek") - a felhasználó explicit kérése, hogy
    # a Project Code-okhoz csak külön, kifejezett jogosultsággal lehessen
    # hozzáférni, ne automatikusan a Projektek jogosultsággal együtt.
    page="/projektek/project-kodok",
    entity_type="projectCode",
    # A ProjectCodeRead számított mezői (osszes_koltseg, becsult_profit)
    # végigjárják a kiadásokat, az utómunkákat és a bevételeket. Eager load
    # nélkül ez SORONKÉNT 3 külön lekérdezést jelentene: 200 projektkódnál
    # 600+ kör, ami a Pénzügyek oldalt másodpercekkel lassította.
    list_options=(
        selectinload(ProjectCode.expenses),
        selectinload(ProjectCode.deliverables),
        selectinload(ProjectCode.revenues),
    ),
)
