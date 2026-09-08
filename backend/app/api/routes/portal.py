from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.security import Role, hash_password
from app.models.portal import Payment, Portal
from app.schemas.portal import PaymentCreate, PaymentRead, PaymentUpdate, PortalCreate, PortalRead, PortalUpdate


def _hash_portal_password(data: dict, db: Session) -> dict:
    password = data.pop("password", None)
    data["password_hash"] = hash_password(password) if password else None
    return data


router = build_crud_router(
    model=Portal,
    create_schema=PortalCreate,
    update_schema=PortalUpdate,
    read_schema=PortalRead,
    prefix="/portal",
    tags=["portal"],
    before_create=_hash_portal_password,
    # A share_token és a jelszóval védett portál adatai nem lehetnek nyilvánosak.
    read_roles=(Role.ADMIN, Role.OPERATOR, Role.VAGO),
)

payments_router = build_crud_router(
    model=Payment,
    create_schema=PaymentCreate,
    update_schema=PaymentUpdate,
    read_schema=PaymentRead,
    prefix="/payments",
    tags=["portal"],
    read_roles=(Role.ADMIN, Role.OPERATOR),
)
