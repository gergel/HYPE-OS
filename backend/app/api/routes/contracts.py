from app.api.crud_router import build_crud_router
from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractRead, ContractUpdate

router = build_crud_router(
    model=Contract,
    create_schema=ContractCreate,
    update_schema=ContractUpdate,
    read_schema=ContractRead,
    prefix="/contracts",
    tags=["contracts"],
    page="/penzugyek",
)
