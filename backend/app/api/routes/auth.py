from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, verify_password
from app.models.employee import Employee
from app.schemas.auth import Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Egy e-mail címhez TÖBB munkatárs is tartozhat (az email szándékosan nem
    # egyedi, lásd models/employee.py), ezért nem az első találatot vesszük -
    # az ugyanis simán lehetne egy jelszó nélküli stáblap-rekord, és a valódi
    # felhasználó nem tudna belépni. Végigpróbáljuk az azonos című fiókokat, és
    # az lép be, amelyiknek a jelszava egyezik; így két, ugyanazt a címet
    # használó ember is a SAJÁT fiókjába jelentkezik be.
    candidates = db.scalars(
        select(Employee).where(Employee.email == form_data.username).order_by(Employee.id)
    ).all()
    user = next(
        (c for c in candidates if c.hashed_password and verify_password(form_data.password, c.hashed_password)),
        None,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hibás email vagy jelszó",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A felhasználó inaktív")
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: Employee = Depends(get_current_user)):
    return current_user
