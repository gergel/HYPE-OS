import os

from fastapi import Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, hash_password, require_page_action, require_roles
from app.models.employee import Employee
from app.models.rate import Rate
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate, RateCreate, RateRead, RateUpdate
from app.services import document_storage


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
    page="/csapat",
    before_create=_hash_employee_password,
)


class SetPasswordPayload(BaseModel):
    password: str


@router.post(
    "/{employee_id}/set-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def set_employee_password(employee_id: int, payload: SetPasswordPayload, db: Session = Depends(get_db)):
    """Admin beállítja/visszaállítja egy meglévő munkatárs jelszavát - erre azért
    van szükség, mert a Notionből importált munkatársaknak sosem volt jelszavuk
    (hashed_password=None), tehát bejelentkezéshez valakinek adminként be kell
    állítania egyet nekik (lásd Beállítások oldal, per-felhasználó rész)."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A jelszónak legalább 6 karakter hosszúnak kell lennie")
    employee.hashed_password = hash_password(payload.password)
    db.commit()


@router.post("/{employee_id}/munkaszerzodes")
async def upload_munkaszerzodes(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    """A munkatárs munkaszerződésének (PDF/Word/kép) feltöltése - egy adott
    munkatárshoz mindig ugyanazt az R2 kulcsot írjuk felül (nincs kiterjedés-
    független fájlnév-ütközés/árva fájl felhalmozódás új feltöltésenként)."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    ext = os.path.splitext(file.filename or "munkaszerzodes.pdf")[1] or ".pdf"
    key = f"munkaszerzodes/{employee_id}{ext}"
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    employee.munkaszerzodes_url = url
    db.commit()
    return {"munkaszerzodes_url": url}


rates_router = build_crud_router(
    model=Rate,
    create_schema=RateCreate,
    update_schema=RateUpdate,
    read_schema=RateRead,
    prefix="/rates",
    tags=["crew"],
    page="/csapat",
)
