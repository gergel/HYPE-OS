from app.api.crud_router import build_crud_router
from app.models.flora_feladat import FloraFeladat
from app.schemas.flora_feladat import FloraFeladatCreate, FloraFeladatRead, FloraFeladatUpdate

router = build_crud_router(
    model=FloraFeladat,
    create_schema=FloraFeladatCreate,
    update_schema=FloraFeladatUpdate,
    read_schema=FloraFeladatRead,
    prefix="/flora",
    tags=["flora"],
    page="/flora",
    entity_type="floraFeladat",
)
