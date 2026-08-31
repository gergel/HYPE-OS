"""Ki felel a diszpó kiküldéséért - oldalanként (gyártás / technika) külön
névsor, a Beállítások oldalról szerkeszthető. A beállított emberek "Teendőim"
widgetjében jelennek meg a MÁSNAPI forgatások diszpói (lásd
api/routes/dashboard.py my_tasks)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_roles
from app.models.dispo_responsible import DispoResponsible, DispoSide, DiszpoMasolatCimzett
from app.models.employee import Employee

router = APIRouter(prefix="/dispo-responsibles", tags=["dispo"])


class MasolatCimzettekPayload(BaseModel):
    """Kik kapják MÁSOLATBAN az összes kimenő diszpót - a mentés teljes csere."""

    employee_ids: list[int] = []


@router.get("/masolat", response_model=MasolatCimzettekPayload)
def get_masolat_cimzettek(
    db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
) -> MasolatCimzettekPayload:
    return MasolatCimzettekPayload(
        employee_ids=[r.employee_id for r in db.scalars(select(DiszpoMasolatCimzett)).all()]
    )


@router.put("/masolat", response_model=MasolatCimzettekPayload)
def set_masolat_cimzettek(
    payload: MasolatCimzettekPayload,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_roles(Role.ADMIN)),
) -> MasolatCimzettekPayload:
    """A diszpó másolat-címzettek listájának cseréje - csak admin (a
    Beállítások oldalról, lásd frontend DiszpoMasolatManager). Az itt megadott
    emberek email címe minden kimenő diszpóra (előzetes és teljes) CC-ként
    kerül rá (lásd services/dispo.py masolat_cimzettek)."""
    db.query(DiszpoMasolatCimzett).delete()
    letezok = set(db.scalars(select(Employee.id).where(Employee.id.in_(payload.employee_ids))).all())
    for employee_id in dict.fromkeys(payload.employee_ids):  # sorrendtartó duplikátum-szűrés
        if employee_id in letezok:
            db.add(DiszpoMasolatCimzett(employee_id=employee_id))
    db.commit()
    return MasolatCimzettekPayload(
        employee_ids=[r.employee_id for r in db.scalars(select(DiszpoMasolatCimzett)).all()]
    )


class DispoResponsiblesPayload(BaseModel):
    """Oldalanként a felelősök employee_id listája - a mentés teljes cserét
    jelent (a listából kihagyott ember felelőssége megszűnik)."""

    gyartas: list[int] = []
    technika: list[int] = []


def _current(db: Session) -> DispoResponsiblesPayload:
    rows = db.scalars(select(DispoResponsible)).all()
    return DispoResponsiblesPayload(
        gyartas=[r.employee_id for r in rows if r.oldal == DispoSide.GYARTAS],
        technika=[r.employee_id for r in rows if r.oldal == DispoSide.TECHNIKA],
    )


@router.get("", response_model=DispoResponsiblesPayload)
def get_responsibles(
    db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
) -> DispoResponsiblesPayload:
    return _current(db)


@router.put("", response_model=DispoResponsiblesPayload)
def set_responsibles(
    payload: DispoResponsiblesPayload,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_roles(Role.ADMIN)),
) -> DispoResponsiblesPayload:
    db.query(DispoResponsible).delete()
    # Ugyanaz az ember MINDKÉT oldalon szerepelhet - ilyenkor két külön teendőt
    # kap, mert a kettő más-más feltétellel kerül le (lásd DispoSide docstring).
    for side, ids in ((DispoSide.GYARTAS, payload.gyartas), (DispoSide.TECHNIKA, payload.technika)):
        for employee_id in dict.fromkeys(ids):  # sorrendtartó duplikátum-szűrés
            db.add(DispoResponsible(employee_id=employee_id, oldal=side))
    db.commit()
    return _current(db)
