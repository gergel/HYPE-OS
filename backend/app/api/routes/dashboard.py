"""Dashboard modul - a mockup összegző kártyáinak valós lekérdezései."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.dashboard_config import DashboardConfig
from app.models.deliverable import Deliverable
from app.models.dispo_responsible import DispoResponsible, DispoSide
from app.models.employee import Employee, SystemRole
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
    #: Melyik "mappába" tartozik a teendő (pl. "Belsős TIG") - a papírozás
    #: listája így nem 400 sorként ömlik a dashboardra, hanem csoportosítva
    #: jelenik meg (lásd frontend MyTasksCard).
    csoport: str | None = None


class MyTasksSummary(BaseModel):
    deliverables: list[MyTaskItem]
    tasks: list[MyTaskItem]
    # A másnapi forgatások diszpói, ha a felhasználó diszpó-felelős (lásd
    # models/dispo_responsible.py). Külön lista, mert nem egy Feladat/Utómunka
    # rekordból jön, hanem a forgatás diszpó-állapotából származtatjuk.
    diszpok: list[MyTaskItem] = []
    # A projektek "papírozása" (belsős TIG, külsős TIG + alvállalkozói
    # szerződés, megrendelői szerződés + TIG) - csak az Adminisztráció
    # szerepkörűeknek, lásd _papirozas_tasks.
    papirozas: list[MyTaskItem] = []


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
        diszpok=_tomorrow_dispo_tasks(db, current_user),
        papirozas=_papirozas_tasks(db, current_user),
    )


def _papirozas_tasks(db: Session, user: Employee) -> list[MyTaskItem]:
    """A projektek teljes "papírozása" teendőként - CSAK az Adminisztráció
    szerepkörűeknek (lásd models/employee.SystemRole.ADMINISZTRACIO).

    Három terület, ugyanaz, amit a saját oldalaik mutatnak - itt csak
    összegyűjtve, hogy egy helyen látszódjon, mi maradt hátra:

      1. Belsős TIG - havonta, mindenkinek (lásd belsos-tig/attekintes),
      2. Külsős TIG + alvállalkozói szerződés a diszpózott projektekhez
         (lásd Utókövetés),
      3. a megrendelő felé menő szerződés és TIG projektkódonként.

    Szándékosan a MÁR ESEDÉKES tételek jönnek: a belsős TIG-nél csak az a
    hónap, aminek a határideje elérkezett (a jövő havi TIG-et még nem lehet
    elkészíteni), a megrendelői TIG-nél pedig csak az a projektkód, amin már
    volt kiküldött diszpójú forgatás - amíg a munka el sem kezdődött, nincs
    mit igazolni."""
    if user.role != SystemRole.ADMINISZTRACIO:
        return []

    # A körkörös import elkerülésére a hívás helyén importálunk: ezek a modulok
    # a saját területük logikáját tartják karban, itt csak felhasználjuk őket.
    from app.api.routes.internal_performance_certificates import havi_attekintes
    from app.api.routes.utokovetes_admin import list_utokovetes_overview

    today = date.today()
    items: list[MyTaskItem] = []

    # 1. Belsős TIG - hónaponként egy tétel, a hiányzók számával.
    for honap in havi_attekintes(honapok=6, db=db, _user=user):
        if honap.allapot == "lezarva" or honap.hatarido > today:
            continue
        items.append(
            MyTaskItem(
                id=honap.ev * 100 + honap.honap,
                title=f"{honap.honap_szoveg}: {honap.hianyzo} hiányzik",
                hatarido=honap.hatarido,
                link=f"/belsos-tig?ev={honap.ev}&honap={honap.honap}",
                csoport="Belsős TIG",
            )
        )

    # 2. Külsős TIG + alvállalkozói szerződés (Utókövetés) - projektenként
    #    külön tétel a kettőre, mert két külön elvégzendő dolog.
    for sor in list_utokovetes_overview(db=db, _user=user):
        nev = sor.project_nev or f"Projekt #{sor.project_id}"
        if sor.szerzodes_fuggo > 0:
            items.append(
                MyTaskItem(
                    id=sor.project_id,
                    title=f"{nev}: {sor.szerzodes_fuggo} hiányzik",
                    hatarido=sor.forgatas_datuma,
                    link=f"/utokovetes/{sor.project_id}",
                    csoport="Alvállalkozói szerződés",
                )
            )
        if sor.tig_ready and sor.tig_fuggo > 0:
            items.append(
                MyTaskItem(
                    id=sor.project_id,
                    title=f"{nev}: {sor.tig_fuggo} hiányzik",
                    hatarido=sor.forgatas_datuma,
                    link=f"/utokovetes/{sor.project_id}",
                    csoport="Külsős TIG",
                )
            )

    # 3. Megrendelői szerződés és TIG - projektkódonként.
    for pc in db.scalars(select(ProjectCode).order_by(ProjectCode.projektkod)):
        if pc.contract_id is None:
            items.append(
                MyTaskItem(
                    id=pc.id,
                    title=pc.projektkod,
                    hatarido=pc.datum,
                    link=f"/projektek/project-kodok/{pc.id}",
                    csoport="Megrendelői szerződés",
                )
            )
        # TIG csak akkor, ha a munka már el is indult (volt kiküldött diszpójú
        # forgatás) - enélkül minden jövőbeli projektkód örökre teendő lenne.
        elif not pc.tig_kikuldve and any(p.diszpo == "Kiküldve" for p in pc.projects):
            items.append(
                MyTaskItem(
                    id=pc.id,
                    title=pc.projektkod,
                    hatarido=pc.datum,
                    link=f"/projektek/project-kodok/{pc.id}",
                    csoport="Megrendelői TIG",
                )
            )

    # A legrégebbi határidő elöl (a dátum nélküliek a végén) - ami régebb óta
    # húzódik, azzal kell előbb foglalkozni.
    return sorted(items, key=lambda i: (i.hatarido is None, i.hatarido or today))


def _tomorrow_dispo_tasks(db: Session, user: Employee) -> list[MyTaskItem]:
    """A MÁSNAPI forgatások diszpói teendőként, ha a felhasználó diszpó-felelős.

    A két oldal külön tétel, mert külön feltétellel kerül le a listáról:

    - gyártás: az előzetes diszpó kiküldésével kész. Ha viszont a TELJES diszpó
      már kiment (akár előzetes nélkül), akkor sincs több teendő - a felhasználó
      kifejezett kérése, hogy ilyenkor a gyártástól is tűnjön el.
    - technika: KIZÁRÓLAG a teljes diszpó kiküldésével kész; az előzetes
      önmagában nem számít, mert a technika lista abban még nem megy ki.

    Aki mindkét oldalon felelős, két tételt lát ugyanarra a forgatásra, amíg
    mindkettő nyitva van - szándékosan, mert két külön elvégzendő dologról van
    szó."""
    sides = set(
        db.scalars(select(DispoResponsible.oldal).where(DispoResponsible.employee_id == user.id)).all()
    )
    if not sides:
        return []

    tomorrow = date.today() + timedelta(days=1)
    projects = db.scalars(
        select(Project)
        .where(Project.forgatas_datuma == tomorrow)
        # A meetingek/helyszínbejárások (a naptárban lila események) nem
        # diszponálandók - lásd services/google_calendar.py.
        .where(Project.nem_diszponalando.is_(False))
        .order_by(Project.nev)
    ).all()

    # Ha egy több napos forgatásból leválasztottuk a holnapi napot, akkor azt a
    # NAPOT kell diszponálni, nem az egészet - az eredeti projekt ilyenkor nem
    # jön fel teendőként (lásd services/project_actions.create_feldarabolas).
    # A darabolás vissza is vágja az eredeti záró napját, tehát ez jellemzően
    # már nem is fordulhat elő - a régebbi, darabolás előtti adatoknál viszont
    # igen, ezért itt is kiszűrjük.
    szulo_idk = {p.feldarabolas_szulo_id for p in projects if p.feldarabolas_szulo_id is not None}

    items: list[MyTaskItem] = []
    for p in projects:
        if p.id in szulo_idk:
            continue
        teljes_kiment = bool(p.diszpo)
        elozetes_kiment = bool(p.elozetes_diszpo_kuldes)
        if DispoSide.GYARTAS in sides and not elozetes_kiment and not teljes_kiment:
            items.append(
                MyTaskItem(
                    id=p.id,
                    title=f"Előzetes diszpó (gyártás): {p.nev}",
                    hatarido=p.forgatas_datuma,
                    link=f"/projektek/{p.id}",
                )
            )
        if DispoSide.TECHNIKA in sides and not teljes_kiment:
            items.append(
                MyTaskItem(
                    id=p.id,
                    title=f"Teljes diszpó (technika): {p.nev}",
                    hatarido=p.forgatas_datuma,
                    link=f"/projektek/{p.id}",
                )
            )
    return items


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
