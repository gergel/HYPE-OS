from app.api.crud_router import build_crud_router
from app.models.client import Client, Contact
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate, ContactCreate, ContactRead, ContactUpdate

router = build_crud_router(
    model=Client,
    create_schema=ClientCreate,
    update_schema=ClientUpdate,
    read_schema=ClientRead,
    prefix="/clients",
    tags=["clients"],
    page="/ugyfelek",
    entity_type="client",
)

contacts_router = build_crud_router(
    model=Contact,
    create_schema=ContactCreate,
    update_schema=ContactUpdate,
    read_schema=ContactRead,
    prefix="/contacts",
    tags=["clients"],
    page="/ugyfelek",
)
