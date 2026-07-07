import os

from fastapi import Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, get_current_user, hash_password, require_page_action, require_roles
from app.models.employee import Employee
from app.models.employee_document import EmployeeDocument
from app.models.rate import Rate
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeDocumentRead,
    EmployeeRead,
    EmployeeUpdate,
    RateCreate,
    RateRead,
    RateUpdate,
)
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


@router.get("/{employee_id}/munkaszerzodesek", response_model=list[EmployeeDocumentRead])
def list_munkaszerzodesek(
    employee_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    return employee.documents


@router.post("/{employee_id}/munkaszerzodesek", response_model=EmployeeDocumentRead)
async def upload_munkaszerzodes(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    """Egy dokumentum (pl. munkaszerződés PDF/Word/kép) feltöltése egy
    munkatárshoz - egy munkatársnak tetszőleges számú fájlja lehet, mindegyik
    saját R2 kulcs alatt (a dokumentum id-ja alapján), egyenként törölhetők."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    filename = file.filename or "dokumentum"
    content_type = file.content_type or "application/octet-stream"
    doc = EmployeeDocument(employee_id=employee_id, filename=filename, content_type=content_type, storage_key="", url="")
    db.add(doc)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"munkaszerzodes/{employee_id}/{doc.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    doc.storage_key = key
    doc.url = url
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{employee_id}/munkaszerzodesek/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_munkaszerzodes(
    employee_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    doc = db.get(EmployeeDocument, document_id)
    if doc is None or doc.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="A dokumentum nem található")
    document_storage.delete_object(doc.storage_key)
    db.delete(doc)
    db.commit()


rates_router = build_crud_router(
    model=Rate,
    create_schema=RateCreate,
    update_schema=RateUpdate,
    read_schema=RateRead,
    prefix="/rates",
    tags=["crew"],
    page="/csapat",
)
