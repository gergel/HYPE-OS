from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.employee import Employee
from app.models.user_access import PageAccessConfig
from app.schemas.user_access import MyAccess, PageAccessRead, PageAccessUpdate

router = APIRouter(prefix="/user-access", tags=["user-access"])


@router.get("/me", response_model=MyAccess)
def get_my_access(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    """A bejelentkezett felhasználó saját oldal-hozzáférése - ezt bárki lekérdezheti
    saját magára (a middleware és a Sidebar ez alapján szűr), de nem módosíthatja."""
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == current_user.id))
    return MyAccess(allowed_pages=config.allowed_pages if config else None)


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
        config = PageAccessConfig(employee_id=employee_id, allowed_pages=payload.allowed_pages)
        db.add(config)
    else:
        config.allowed_pages = payload.allowed_pages
    db.commit()
    db.refresh(config)
    return config
