from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.employee import Employee, SystemRole as Role
from app.models.user_access import PageAccessConfig

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen vagy lejárt token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Employee:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Érvénytelen token")
    user = db.get(Employee, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Felhasználó nem található")
    return user


def require_roles(*roles: Role):
    def dependency(current_user: Employee = Depends(get_current_user)) -> Employee:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nincs jogosultságod ehhez a művelethez",
            )
        return current_user

    return dependency


def check_page_action(db: Session, employee: Employee, page: str, action: str) -> None:
    """A durvább admin/operator szerepkör-ellenőrzés (lásd require_roles) UTÁN
    hívva a finomabb, oldal+művelet-szintű írási jogosultságot ellenőrzi - ha
    az alkalmazottnak van PageAccessConfig sora ÉS abban page_permissions be
    van állítva, csak azokon az oldalakon/műveleteken enged, amiket admin
    kifejezetten megadott neki (lásd Beállítások oldal). Ha nincs sora, vagy a
    page_permissions None, korlátozás nélkül enged (ugyanaz az alapértelmezett
    viselkedés, mint az oldal-láthatóságnál)."""
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
    if config is None or config.page_permissions is None:
        return
    allowed = config.page_permissions.get(page)
    if allowed is None or action not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nincs jogosultságod ehhez a művelethez ezen az oldalon.",
        )


def check_tab_action(db: Session, employee: Employee, page: str, tab_key: str, action: str) -> None:
    """A részletnézet-fülek (lásd models/detail_tab.py) szintjén finomítja a
    check_page_action-t: a "{page}:{tab_key}" összetett kulcs csak akkor
    SZŰKÍTI a jogosultságot, ha admin kifejezetten beállította azt a
    munkatársnak (lásd Beállítások oldal, UserAccessManager fülenkénti
    Látja/Szerkesztheti checkboxai) - ha nincs ilyen összetett kulcs a
    page_permissions dict-ben, az adott fül a MEGLÉVŐ, oldal-szintű jogot
    örökli (nem esik vissza tiltásra). Enélkül minden olyan munkatárs, akinek
    admin BÁRMELYIK oldalhoz korlátozást állított be (page_permissions nem
    None), az ÖSSZES részletnézet-fülön elveszítené a hozzáférést minden
    olyan fülhöz, amihez admin még nem konfigurált explicit fül-szintű
    engedélyt - beleértve a bespoke widgeteket (pl. eszközfoglalás, szerződés
    készítés) is, amik nem is mező-szerkesztést jelentenek, hanem önálló
    akció-gombok egy adott fülön belül."""
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
    if config is None or config.page_permissions is None:
        return
    allowed = config.page_permissions.get(f"{page}:{tab_key}")
    if allowed is None:
        allowed = config.page_permissions.get(page)
    if allowed is None or action not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nincs jogosultságod ehhez a művelethez ezen a fülön.",
        )


def require_page_action(page: str, action: str, *write_roles: Role):
    """Standalone (nem build_crud_router-en keresztül regisztrált) végpontokhoz
    - pl. equipment.py Assignment create/delete - ugyanazt az oldal+művelet-
    szintű ellenőrzést adja, mint amit a build_crud_router minden generikus
    create/update/delete végpontja automatikusan megkap."""
    write_roles = write_roles or (Role.ADMIN, Role.OPERATOR)
    role_dependency = require_roles(*write_roles)

    def dependency(current_user: Employee = Depends(role_dependency), db: Session = Depends(get_db)) -> Employee:
        check_page_action(db, current_user, page, action)
        return current_user

    return dependency
