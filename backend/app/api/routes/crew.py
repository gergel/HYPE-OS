from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.security import hash_password
from app.models.employee import Employee
from app.models.rate import Rate
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate, RateCreate, RateRead, RateUpdate


def _hash_employee_password(data: dict, db: Session) -> dict:
    password = data.pop("password")
    data["hashed_password"] = hash_password(password)
    return data


router = build_crud_router(
    model=Employee,
    create_schema=EmployeeCreate,
    update_schema=EmployeeUpdate,
    read_schema=EmployeeRead,
    prefix="/crew",
    tags=["crew"],
    before_create=_hash_employee_password,
)

rates_router = build_crud_router(
    model=Rate,
    create_schema=RateCreate,
    update_schema=RateUpdate,
    read_schema=RateRead,
    prefix="/rates",
    tags=["crew"],
)
