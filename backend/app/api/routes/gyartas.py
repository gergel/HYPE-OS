"""Gyártás-TV — a gyártási szobában kirakott, élő áttekintő (lásd
services/gyartas_tv.py). Csak olvas; a felület néhány másodpercenként kéri le."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, require_page_action
from app.models.employee import Employee
from app.services.gyartas_tv import tv_adatok

router = APIRouter(prefix="/gyartas", tags=["gyartas"])

PAGE = "/gyartas"


@router.get("/tv")
def gyartas_tv(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *tuple(Role))),
):
    """A heti forgatások (kik dolgoznak), ki mit vág épp, mi küldhető ki, és
    hol várnak a gyártásra. Csak olvas."""
    return tv_adatok(db)
