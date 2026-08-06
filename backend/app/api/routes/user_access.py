from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.employee import Employee
from app.models.field_visibility import FieldVisibilityConfig
from app.models.user_access import PageAccessConfig
from app.schemas.user_access import MyAccess, PageAccessRead, PageAccessUpdate

router = APIRouter(prefix="/user-access", tags=["user-access"])


@router.get("/me", response_model=MyAccess)
def get_my_access(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    """A bejelentkezett felhasználó saját oldal-hozzáférése - ezt bárki lekérdezheti
    saját magára (a middleware és a Sidebar ez alapján szűr), de nem módosíthatja."""
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == current_user.id))
    permissions = config.page_permissions if config else None
    allowed_pages = list(permissions.keys()) if permissions is not None else None
    return MyAccess(
        allowed_pages=allowed_pages,
        page_permissions=permissions,
        lathato_deliverable_idk=config.lathato_deliverable_idk if config else None,
    )


@router.get("", response_model=list[PageAccessRead], dependencies=[Depends(require_roles(Role.ADMIN))])
def list_access(db: Session = Depends(get_db)):
    """Az összes munkatárs oldal-hozzáférése egyszerre (Beállítások oldal tölti be)."""
    return db.scalars(select(PageAccessConfig)).all()


@router.put("/{employee_id}", response_model=PageAccessRead, dependencies=[Depends(require_roles(Role.ADMIN))])
def set_access(employee_id: int, payload: PageAccessUpdate, db: Session = Depends(get_db)):
    """Admin beállítja, mely oldalakat láthatja egy adott munkatárs - csak admin
    módosíthatja, maga az érintett felhasználó nem (lásd GET /me, csak olvasás)."""
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee_id))
    if config is None:
        config = PageAccessConfig(employee_id=employee_id, page_permissions=payload.page_permissions)
        db.add(config)
    else:
        config.page_permissions = payload.page_permissions
    # Az anyag-korlátozás külön kapcsoló: None = nincs szűkítés (mindent lát).
    config.lathato_deliverable_idk = payload.lathato_deliverable_idk
    db.commit()
    db.refresh(config)
    return config


@router.delete("/others")
def revoke_access_for_others(current_user: Employee = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    """Admin egy kattintással visszavonja MINDENKI MÁS bejelentkezési hozzáférését
    a sajátja kivételével - a munkatárs-rekordjuk megmarad (nem törlődnek, csak a
    jelszavuk), és az oldal-/mező-hozzáférésük alapértelmezettre áll vissza.
    Admin bármikor újra beállíthatja egyénenként (lásd Beállítások oldal)."""
    other_ids = list(db.scalars(select(Employee.id).where(Employee.id != current_user.id)))
    if other_ids:
        db.query(Employee).filter(Employee.id.in_(other_ids)).update({"hashed_password": None}, synchronize_session=False)
        db.query(PageAccessConfig).filter(PageAccessConfig.employee_id.in_(other_ids)).delete(synchronize_session=False)
        db.query(FieldVisibilityConfig).filter(FieldVisibilityConfig.employee_id.in_(other_ids)).delete(synchronize_session=False)
    db.commit()
    return {"revoked_count": len(other_ids)}


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles(Role.ADMIN))])
def revoke_access(employee_id: int, db: Session = Depends(get_db)):
    """Admin visszavonja egy munkatárs hozzáférését (Beállítások oldal, "Hozzáférés
    törlése" gomb): törli a jelszavát (nem tud többé bejelentkezni), és
    visszaállítja alapértelmezettre (nincs szűrés) az oldal- és mező-hozzáférését."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")
    employee.hashed_password = None
    db.query(PageAccessConfig).filter(PageAccessConfig.employee_id == employee_id).delete()
    db.query(FieldVisibilityConfig).filter(FieldVisibilityConfig.employee_id == employee_id).delete()
    db.commit()
