from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    vedett_rendszergazda,
    verify_password,
)
from app.models.employee import Employee, SystemRole
from app.schemas.auth import TEMAK, TemaIn, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _vedett_fiok_helyreallitasa(user: Employee, db: Session) -> None:
    """A védett rendszergazda fiókját belépéskor VISSZAÁLLÍTJUK.

    A futásidejű ellenőrzések amúgy is átengedik (lásd
    core/security.vedett_rendszergazda), de akkor az adatbázisban ott maradna
    egy inaktív, esetleg nem is admin sor - a Beállítások oldal azt mutatná, a
    következő olvasó pedig azt hinné, tényleg ki van kapcsolva. Belépéskor
    tehát nemcsak beengedjük, hanem rendbe is tesszük a rekordot.

    Ez egyben a javítás útja is: ha a fiókot valaki inaktívra állítja, elég
    újra bejelentkezni - nem kell adatbázishoz nyúlni."""
    valtozott = False
    if not user.is_active:
        user.is_active = True
        valtozott = True
    if user.role != SystemRole.ADMIN:
        user.role = SystemRole.ADMIN
        valtozott = True
    if valtozott:
        db.commit()


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
    # A védett rendszergazdát az inaktív jelölés sem tartja kint - sőt, a
    # belépés vissza is állítja a fiókját (lásd _vedett_fiok_helyreallitasa).
    if vedett_rendszergazda(user):
        _vedett_fiok_helyreallitasa(user, db)
    elif not user.is_active:
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
    lejáratkor kiesik akkor is, ha épp nyitva volt neki az oldal. A védett
    rendszergazda kivétel - az ő munkamenete nem szakadhat meg."""
    if not current_user.is_active and not vedett_rendszergazda(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A felhasználó inaktív")
    return Token(access_token=create_access_token(subject=str(current_user.id), role=current_user.role.value))


def _kimenet(user: Employee) -> UserOut:
    """A védettséget a beállításból számoljuk, nem az adatbázisból - egy oszlop
    itt csak egy újabb dolog lenne, amit el lehet rontani."""
    return UserOut.model_validate(user).model_copy(update={"vedett_admin": vedett_rendszergazda(user)})


@router.get("/me", response_model=UserOut)
def me(current_user: Employee = Depends(get_current_user)):
    return _kimenet(current_user)


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
    return _kimenet(current_user)
