from app.api.crud_router import build_crud_router
from app.models.callsheet import Callsheet
from app.schemas.callsheet import CallsheetCreate, CallsheetRead, CallsheetUpdate

router = build_crud_router(
    model=Callsheet,
    create_schema=CallsheetCreate,
    update_schema=CallsheetUpdate,
    read_schema=CallsheetRead,
    prefix="/callsheets",
    tags=["callsheets"],
    page="/naptar",
)
