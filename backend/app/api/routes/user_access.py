from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    Role,
    elerheto_oldalak,
    get_current_user,
    require_roles,
    vedett_rendszergazda,
)
from app.models.employee import Employee
from app.models.field_visibility import FieldVisibilityConfig
from app.models.user_access import PageAccessConfig
from app.schemas.user_access import MyAccess, PageAccessRead, PageAccessUpdate

router = APIRouter(prefix="/user-access", tags=["user-access"])

#: Amit a védett rendszergazdán tiltunk. Egy helyen, hogy mindhárom hívóhely
#: (oldal-jogosultság, mező-láthatóság, hozzáférés visszavonása) ugyanazt a
#: mondatot adja vissza.
VEDETT_UZENET = (
    "Ez a védett rendszergazda fiók: a hozzáférése nem korlátozható és nem vonható vissza. "
    "Ha át kell adni, előbb a VEDETT_ADMIN_EMAILEK beállítást kell átírni."
)


def _vedett_e_404(db: Session, employee_id: int) -> Employee:
    """A munkatárs lekérése, a védett fiók elutasításával."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")
    if vedett_rendszergazda(employee):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=VEDETT_UZENET)
    return employee


@router.get("/me", response_model=MyAccess)
def get_my_access(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    """A bejelentkezett felhasználó saját oldal-hozzáférése - ezt bárki lekérdezheti
    saját magára (a middleware és a Sidebar ez alapján szűr), de nem módosíthatja.

    A védett rendszergazdának mindig a "nincs korlátozás" választ adjuk: a
    backend úgyis átengedi (lásd core/security.check_page_action), de ha itt
    egy régi, szűkítő sor jönne vissza, a menü és a middleware attól még
    elrejtené előle az oldalakat - vagyis a felületen mégis ki lenne zárva."""
    if vedett_rendszergazda(current_user):
        return MyAccess()
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == current_user.id))
    permissions = config.page_permissions if config else None
    # Az aliaszon át kapott oldalak is beleszámítanak (lásd
    # core/security.elerheto_oldalak): a diszpósnak a projekt és a
    # felszerelés a menüből is elérhető kell legyen, nem csak végponton.
    allowed_pages = elerheto_oldalak(permissions)
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
    módosíthatja, maga az érintett felhasználó nem (lásd GET /me, csak olvasás).

    A védett rendszergazdának nem lehet korlátozást beállítani: a futásidejű
    ellenőrzés úgyis átengedné, de akkor a Beállítások oldal olyat mutatna,
    ami nem igaz - jobb, ha a mentés mondja meg, hogy ez nem így működik."""
    _vedett_e_404(db, employee_id)
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
    Admin bármikor újra beállíthatja egyénenként (lásd Beállítások oldal).

    A védett rendszergazda kimarad belőle: ez a gomb pont az a művelet, ami egy
    félrekattintással mindenkit kizár - a végső kiutat nem viheti magával."""
    vedett_idk = {
        e.id for e in db.scalars(select(Employee).where(Employee.email.is_not(None))) if vedett_rendszergazda(e)
    }
    other_ids = list(
        db.scalars(select(Employee.id).where(Employee.id != current_user.id, Employee.id.not_in(vedett_idk or {-1})))
    )
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
    visszaállítja alapértelmezettre (nincs szűrés) az oldal- és mező-hozzáférését.

    A védett rendszergazdán nem fut le: a jelszó törlésével ő sem tudna
    belépni, és épp az ő fiókja az, aminek mindig működnie kell."""
    employee = _vedett_e_404(db, employee_id)
    employee.hashed_password = None
    db.query(PageAccessConfig).filter(PageAccessConfig.employee_id == employee_id).delete()
    db.query(FieldVisibilityConfig).filter(FieldVisibilityConfig.employee_id == employee_id).delete()
    db.commit()
