"""Dashboard modul - a mockup összegző kártyáinak valós lekérdezései."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.dashboard_config import DashboardConfig
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.finance import Revenue
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.task import Task, task_employees
from app.schemas.dashboard_config import DashboardConfigUpdate, MyDashboardConfig

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class UpcomingEvent(BaseModel):
    id: int
    nev: str
    forgatas_datuma: date | None
    helyszin: str | None


class RevenueMonth(BaseModel):
    month: str
    total: float


class DashboardAlerts(BaseModel):
    lejart_utomunka: int
    lejart_feladat: int


class MyTaskItem(BaseModel):
    id: int
    title: str
    hatarido: date | None
    link: str


class MyTasksSummary(BaseModel):
    deliverables: list[MyTaskItem]
    tasks: list[MyTaskItem]


class DashboardSummary(BaseModel):
    mai_forgatasok: int
    aktiv_project_codeok: int
    equipment_utkozesek: int
    havi_bevetel: float
    upcoming_events: list[UpcomingEvent]
    revenue_trend: list[RevenueMonth]
    alerts: DashboardAlerts


def _last_n_months(today: date, n: int) -> list[tuple[int, int]]:
    """[(év, hónap), ...] a mai hónapig bezárólag, régitől az újig rendezve."""
    months = []
    year, month = today.year, today.month
    for _ in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    today = date.today()

    mai_forgatasok = (
        db.scalar(select(func.count()).select_from(Project).where(Project.forgatas_datuma == today)) or 0
    )
    aktiv_project_codeok = (
        db.scalar(
            select(func.count())
            .select_from(ProjectCode)
            .where(or_(ProjectCode.esemeny_allapota.is_(None), ProjectCode.esemeny_allapota != "lezarva"))
        )
        or 0
    )
    havi_bevetel = (
        db.scalar(
            select(func.coalesce(func.sum(Revenue.brutto), 0)).where(
                extract("year", Revenue.fizetes_datuma) == today.year,
                extract("month", Revenue.fizetes_datuma) == today.month,
            )
        )
        or 0
    )

    upcoming_rows = db.scalars(
        select(Project)
        .where(Project.forgatas_datuma.is_not(None), Project.forgatas_datuma >= today)
        .order_by(Project.forgatas_datuma.asc())
        .limit(5)
    ).all()
    upcoming_events = [
        UpcomingEvent(id=p.id, nev=p.nev, forgatas_datuma=p.forgatas_datuma, helyszin=p.helyszin) for p in upcoming_rows
    ]

    revenue_by_month: dict[tuple[int, int], float] = {}
    months = _last_n_months(today, 6)
    min_year, min_month = months[0]
    rows = db.execute(
        select(
            extract("year", Revenue.fizetes_datuma).label("y"),
            extract("month", Revenue.fizetes_datuma).label("m"),
            func.coalesce(func.sum(Revenue.brutto), 0).label("total"),
        )
        .where(Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= date(min_year, min_month, 1))
        .group_by("y", "m")
    ).all()
    for row in rows:
        revenue_by_month[(int(row.y), int(row.m))] = float(row.total)
    revenue_trend = [
        RevenueMonth(month=f"{y:04d}-{m:02d}", total=revenue_by_month.get((y, m), 0.0)) for y, m in months
    ]

    lejart_utomunka = (
        db.scalar(
            select(func.count())
            .select_from(Deliverable)
            .where(Deliverable.hatarido.is_not(None), Deliverable.hatarido < today, Deliverable.anyag_kikuldve.is_(False))
        )
        or 0
    )
    lejart_feladat = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.hatarido.is_not(None), Task.hatarido < today, Task.checked.is_(False))
        )
        or 0
    )

    return DashboardSummary(
        mai_forgatasok=mai_forgatasok,
        aktiv_project_codeok=aktiv_project_codeok,
        # az Equipment modul már felvételkor (POST /assignments) elutasítja az ütköző
        # foglalást (409), tehát a DB-ben soha nincs ütköző pár - ez a kártya ezt jelzi
        equipment_utkozesek=0,
        havi_bevetel=float(havi_bevetel),
        upcoming_events=upcoming_events,
        revenue_trend=revenue_trend,
        alerts=DashboardAlerts(lejart_utomunka=lejart_utomunka, lejart_feladat=lejart_feladat),
    )


@router.get("/my-tasks", response_model=MyTasksSummary)
def my_tasks(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """A "Teendőim" dashboard-widget adatai - a bejelentkezett felhasználóra
    kiosztott, még nyitott Utómunkák és Feladatok, hogy egy helyen lássa, mivel
    kell foglalkoznia."""
    deliverables = db.scalars(
        select(Deliverable)
        .where(Deliverable.assigned_to_employee_id == current_user.id, Deliverable.anyag_kikuldve.is_(False))
        .order_by(Deliverable.hatarido.asc().nulls_last())
    ).all()
    tasks = db.scalars(
        select(Task)
        .join(task_employees, task_employees.c.task_id == Task.id)
        .where(task_employees.c.employee_id == current_user.id, Task.checked.is_(False))
        .order_by(Task.hatarido.asc().nulls_last())
    ).all()
    return MyTasksSummary(
        deliverables=[
            MyTaskItem(id=d.id, title=d.projekt_neve or f"Anyag #{d.id}", hatarido=d.hatarido, link=f"/utomunka/{d.id}")
            for d in deliverables
        ],
        tasks=[MyTaskItem(id=t.id, title=t.feladat, hatarido=t.hatarido, link="/feladatok") for t in tasks],
    )


@router.get("/config/me", response_model=MyDashboardConfig)
def get_my_dashboard_config(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    """A bejelentkezett felhasználó saját Dashboard widget-beállítása - tisztán
    megjelenítési preferencia, ezért bárki szabadon szerkesztheti a sajátját
    (nincs admin-gate, ellentétben a jelszó/oldal/mező-hozzáféréssel)."""
    config = db.scalar(select(DashboardConfig).where(DashboardConfig.employee_id == current_user.id))
    return MyDashboardConfig(visible_widgets=config.visible_widgets if config else None)


@router.put("/config/me", response_model=MyDashboardConfig)
def set_my_dashboard_config(
    payload: DashboardConfigUpdate, current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)
):
    config = db.scalar(select(DashboardConfig).where(DashboardConfig.employee_id == current_user.id))
    if config is None:
        config = DashboardConfig(employee_id=current_user.id, visible_widgets=payload.visible_widgets)
        db.add(config)
    else:
        config.visible_widgets = payload.visible_widgets
    db.commit()
    db.refresh(config)
    return MyDashboardConfig(visible_widgets=config.visible_widgets)
