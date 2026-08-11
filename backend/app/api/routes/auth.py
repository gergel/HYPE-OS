from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, verify_password
from app.models.employee import Employee
from app.schemas.auth import TEMAK, TemaIn, Token, UserOut

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


@router.post("/refresh", response_model=Token)
def refresh(current_user: Employee = Depends(get_current_user)):
    """GÖRDÜLŐ munkamenet: érvényes tokenért cserébe ad egy frisset, újraindított
    lejárattal. A frontend middleware hívja meg, amikor a token már a
    lejárati idejének felénél jár - így aki használja a rendszert, sosem esik
    ki, viszont aki hónapokig nem lép be, annak lejár a hozzáférése.

    Az inaktívvá tett munkatárs itt akad fenn: a tokene nem újul meg, tehát a
    lejáratkor kiesik akkor is, ha épp nyitva volt neki az oldal."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A felhasználó inaktív")
    return Token(access_token=create_access_token(subject=str(current_user.id), role=current_user.role.value))


@router.get("/me", response_model=UserOut)
def me(current_user: Employee = Depends(get_current_user)):
    return current_user


@router.put("/me/tema", response_model=UserOut)
def set_tema(
    payload: TemaIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """A felület témájának (világos/sötét) mentése a BEJELENTKEZETT emberhez.

    Önkiszolgáló, mint a Dashboard widget-beállítás: tisztán megjelenítési
    preferencia, mindenki csak a sajátját írja (a rekordot a tokenből kapjuk,
    nem az útvonalból), ezért nincs hozzá oldal-jogosultság.

    Azért a szerveren tároljuk és nem a böngészőben, mert a választás az
    EMBERHEZ tartozik: aki otthon világosra állítja, az az irodai gépen is
    világosat vár, egy közös gépen pedig a következő belépő ne örökölje az
    előző ízlését."""
    if payload.tema not in TEMAK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ismeretlen téma. Választható: {', '.join(TEMAK)}",
        )
    current_user.tema = payload.tema
    db.commit()
    db.refresh(current_user)
    return current_user
