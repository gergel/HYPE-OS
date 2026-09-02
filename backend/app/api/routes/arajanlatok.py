"""Árajánlat-készítő: mentett ajánlatok/sablonok + alap tétel-katalógus.

Mindkét entitás az "/arajanlatok" oldal joga alatt áll - az oldalhoz a
Beállítások oldalon KÜLÖN adható hozzáférés (a felhasználó kérése), és aki
megkapta, az a katalógust is szerkesztheti (write_roles = minden szerepkör,
a valódi kapu az oldal-jog)."""

from app.api.crud_router import build_crud_router
from app.core.security import Role
from app.models.arajanlat import Arajanlat, ArajanlatTetel
from app.schemas.arajanlat import (
    ArajanlatCreate,
    ArajanlatListItem,
    ArajanlatRead,
    ArajanlatTetelCreate,
    ArajanlatTetelRead,
    ArajanlatTetelUpdate,
    ArajanlatUpdate,
)

PAGE = "/arajanlatok"
_MINDEN_SZEREPKOR = tuple(Role)

router = build_crud_router(
    model=Arajanlat,
    create_schema=ArajanlatCreate,
    update_schema=ArajanlatUpdate,
    read_schema=ArajanlatRead,
    list_read_schema=ArajanlatListItem,
    prefix="/arajanlatok",
    tags=["arajanlatok"],
    page=PAGE,
    write_roles=_MINDEN_SZEREPKOR,
)

tetel_router = build_crud_router(
    model=ArajanlatTetel,
    create_schema=ArajanlatTetelCreate,
    update_schema=ArajanlatTetelUpdate,
    read_schema=ArajanlatTetelRead,
    prefix="/arajanlat-tetelek",
    tags=["arajanlatok"],
    page=PAGE,
    write_roles=_MINDEN_SZEREPKOR,
)
