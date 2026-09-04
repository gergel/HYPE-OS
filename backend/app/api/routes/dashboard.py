"""Dashboard modul - a mockup összegző kártyáinak valós lekérdezései."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.auto import Auto, AutoTeendo
from app.models.dashboard_config import DashboardConfig
from app.models.deliverable import Deliverable
from app.models.hype_todo import HypeTodoItem, hype_todo_felelosok
from app.models.deliverable_status import DeliverableStatusConfig
from app.models.dispo_responsible import DispoResponsible, DispoSide
from app.models.employee import Employee, EmployeeType, SystemRole, van_szerepkore
from app.services import elszamolas
from app.services import kotelezettseg as kotelezettseg_szolg
from app.services import megrendeloi_papir
from app.services import papirozas_feladatok
from app.services import papirozas_hatokor
from app.services import vagoi_jatek as vagoi_jatek_szolg
from app.services.hu_datum import budapesti_ma, honap_neve
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
    # A rád osztott AUTÓ-TEENDŐK (lásd models/auto.AutoTeendo) és a HYPE
    # TO-DO feladataid - a felhasználó kérése, hogy ezek is itt legyenek.
    auto_teendok: list[MyTaskItem] = []
    hype_todok: list[MyTaskItem] = []
    # A másnapi forgatások diszpói, ha a felhasználó diszpó-felelős (lásd
    # models/dispo_responsible.py). Külön lista, mert nem egy Feladat/Utómunka
    # rekordból jön, hanem a forgatás diszpó-állapotából származtatjuk.
    diszpok: list[MyTaskItem] = []
    # A projektek "papírozása" (belsős TIG, külsős TIG + alvállalkozói
    # szerződés, megrendelői szerződés + TIG) - csak az Adminisztráció
    # szerepkörűeknek, lásd _papirozas_tasks.
    papirozas: list[MyTaskItem] = []


class VagoiJatekNyertes(BaseModel):
    """A bejelentkezett felhasználó MEGNYERTE az előző havi vágói játékot -
    a dashboard a kihirdetéstől 5 napig ünneplő widgetet mutat neki ebből."""

    ev: int
    honap: int
    honap_nev: str
    pont: int
    nyeremeny: str | None = None
    kep_url: str | None = None


class VagoiUjNyeremeny(BaseModel):
    """A FOLYÓ hónap frissen kihirdetett nyereménye - a kihirdetéstől 5 napig
    minden aktív vágó dashboardján megjelenik (a felhasználó kérése)."""

    honap_nev: str
    nyeremeny: str
    megjegyzes: str | None = None
    kep_url: str | None = None


class DashboardSummary(BaseModel):
    mai_forgatasok: int
    aktiv_project_codeok: int
    equipment_utkozesek: int
    havi_bevetel: float
    upcoming_events: list[UpcomingEvent]
    revenue_trend: list[RevenueMonth]
    alerts: DashboardAlerts
    #: Csak a győztesnek, a kihirdetés utáni 5 napban - egyébként None.
    vagoi_jatek_nyertes: VagoiJatekNyertes | None = None
    #: True, ha a felhasználó admin, és a FOLYÓ hónap vágói-játék nyereménye
    #: még nincs kihirdetve - a dashboard ebből mutat neki bekérő widgetet.
    vagoi_jatek_nyeremeny_bekeres: bool = False
    #: Az aktív vágóknak, a nyeremény kihirdetése utáni 5 napban - egyébként
    #: None.
    vagoi_jatek_uj_nyeremeny: VagoiUjNyeremeny | None = None


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
def summary(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)):
    today = date.today()

    # A lefutott projektek papírozás-feladatai. Ütemező nincs a rendszerben,
    # ezért itt "érjük utol" a lemaradást - a művelet idempotens, projektenként
    # legfeljebb egy feladat születik (lásd services/papirozas_feladatok.py).
    papirozas_feladatok.ensure_papirozas_feladatok(db)

    # Ugyanezért fut itt a kötelezettségek (előfizetés, biztosítás, forgalmi)
    # utolérése is: a fordulóhoz közeledve feladat és értesítés keletkezik a
    # felelősnek, és megnyílnak az esedékes fordulók, amikhez összeget és
    # számlát várunk (lásd services/kotelezettseg.py).
    kotelezettseg_szolg.ensure_mindent(db)

    # És ugyanígy a vágói játék hónapzárása: az új hónap első lekérése hirdeti
    # ki az előző hónap győztesét (értesítéssel), és kéri be az adminoktól az
    # új havi nyereményt (lásd services/vagoi_jatek.havi_zaras).
    vagoi_jatek_szolg.havi_zaras(db)

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
    # Nettóban - ahogy a Pénzügyek összesítője és a projektek profitja is
    # (lásd services/elszamolas.py).
    havi_bevetel = (
        db.scalar(
            select(func.coalesce(func.sum(elszamolas.netto_sql(Revenue)), 0)).where(
                extract("year", Revenue.fizetes_datuma) == today.year,
                extract("month", Revenue.fizetes_datuma) == today.month,
                elszamolas.bevetel_beleszamit_sql(Revenue),
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
            func.coalesce(func.sum(elszamolas.netto_sql(Revenue)), 0).label("total"),
        )
        .where(
            Revenue.fizetes_datuma.is_not(None),
            Revenue.fizetes_datuma >= date(min_year, min_month, 1),
            elszamolas.bevetel_beleszamit_sql(Revenue),
        )
        .group_by("y", "m")
    ).all()
    for row in rows:
        revenue_by_month[(int(row.y), int(row.m))] = float(row.total)
    revenue_trend = [
        RevenueMonth(month=f"{y:04d}-{m:02d}", total=revenue_by_month.get((y, m), 0.0)) for y, m in months
    ]

    # Ami ELKÉSZÜLT, az nem lejárt határidő - hiába van a határideje a
    # múltban. Melyik állapot számít elkészültnek, azt az admin állítja be az
    # Utómunka tábláján (lásd models/deliverable_status.py); alapból a
    # kiküldött anyag számít csak késznek.
    kesz_allapotok = list(
        db.scalars(
            select(DeliverableStatusConfig.allapot).where(DeliverableStatusConfig.kesz_allapot.is_(True))
        ).all()
    )
    lejart_feltetelek = [
        Deliverable.hatarido.is_not(None),
        Deliverable.hatarido < today,
        Deliverable.anyag_kikuldve.is_(False),
    ]
    if kesz_allapotok:
        lejart_feltetelek.append(
            or_(Deliverable.allapot.is_(None), Deliverable.allapot.not_in(kesz_allapotok))
        )
    lejart_utomunka = db.scalar(select(func.count()).select_from(Deliverable).where(*lejart_feltetelek)) or 0
    lejart_feladat = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.hatarido.is_not(None),
                Task.hatarido < today,
                Task.checked.is_(False),
                # Az ARCHIVÁLT feladat nem lejárt teendő (a felhasználó
                # kérése): az "Archive feladatok" importból jött sorok
                # allapot="archived" jelölést hordoznak (lásd
                # notion_import/importers.import_tasks).
                or_(Task.allapot.is_(None), func.lower(Task.allapot) != "archived"),
            )
        )
        or 0
    )

    # Vágói játék: ünneplő widget a győztesnek (a kihirdetéstől 5 napig), és
    # nyeremény-bekérő az adminnak, amíg a folyó hónap nyereménye hiányzik.
    # A hónap-fordulót BUDAPESTI idő szerint nézzük (a felhasználó kérése) -
    # a szerver UTC-órája magyar éjfél után még az előző hónapot mutatná.
    jatek_ma = budapesti_ma()
    nyertes: VagoiJatekNyertes | None = None
    elozo_ev, elozo_ho = vagoi_jatek_szolg.elozo_honap(jatek_ma)
    elozo_sor = vagoi_jatek_szolg.honap_beallitas(db, elozo_ev, elozo_ho)
    if (
        elozo_sor is not None
        and elozo_sor.gyoztes_employee_id == user.id
        and elozo_sor.kihirdetve_at is not None
    ):
        kihirdetve = elozo_sor.kihirdetve_at
        if kihirdetve.tzinfo is None:
            kihirdetve = kihirdetve.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - kihirdetve <= timedelta(days=vagoi_jatek_szolg.GYOZTES_WIDGET_NAPOK):
            nyertes = VagoiJatekNyertes(
                ev=elozo_ev,
                honap=elozo_ho,
                honap_nev=honap_neve(elozo_ho),
                pont=elozo_sor.gyoztes_pont or 0,
                nyeremeny=elozo_sor.nyeremeny,
                kep_url=elozo_sor.kep_url,
            )
    folyo_sor = vagoi_jatek_szolg.honap_beallitas(db, jatek_ma.year, jatek_ma.month)
    nyeremeny_bekeres = False
    if van_szerepkore(user, SystemRole.ADMIN):
        nyeremeny_bekeres = folyo_sor is None or not folyo_sor.nyeremeny

    # A frissen kihirdetett HAVI NYEREMÉNY az aktív vágóknak - a kihirdetéstől
    # 5 napig (a felhasználó kérése). Vágó az, akinek vágó a típusa VAGY a
    # szerepköre: a kettő nem mindig jár együtt (van vágó szerepkörű belsős).
    uj_nyeremeny: VagoiUjNyeremeny | None = None
    vago_e = user.is_active and (user.tipus == EmployeeType.VAGO or van_szerepkore(user, SystemRole.VAGO))
    if (
        vago_e
        and folyo_sor is not None
        and folyo_sor.nyeremeny
        and folyo_sor.nyeremeny_kihirdetve_at is not None
    ):
        kihirdetve = folyo_sor.nyeremeny_kihirdetve_at
        if kihirdetve.tzinfo is None:
            kihirdetve = kihirdetve.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - kihirdetve <= timedelta(days=vagoi_jatek_szolg.GYOZTES_WIDGET_NAPOK):
            uj_nyeremeny = VagoiUjNyeremeny(
                honap_nev=honap_neve(jatek_ma.month),
                nyeremeny=folyo_sor.nyeremeny,
                megjegyzes=folyo_sor.megjegyzes,
                kep_url=folyo_sor.kep_url,
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
        vagoi_jatek_nyertes=nyertes,
        vagoi_jatek_nyeremeny_bekeres=nyeremeny_bekeres,
        vagoi_jatek_uj_nyeremeny=uj_nyeremeny,
    )


class SajatDiszpo(BaseModel):
    """Egy diszpó, amin a bejelentkezett munkatárs rajta van (a stábban) - a
    dashboard "Mai/Holnapi diszpód" kártyája és a Diszpóim gyűjtő oldal
    használja (a felhasználó kérése). SZÁNDÉKOSAN csak a név, a dátum és a
    PDF: a diszpó többi adatát a stábtag innen nem látja."""

    project_id: int
    projekt_nev: str | None
    forgatas_datuma: date | None
    forgatas_vege: date | None
    #: A kiküldött diszpó PDF-je (Drive link) - None, amíg nincs kiküldve.
    pdf_url: str | None


@router.get("/sajat-diszpok", response_model=list[SajatDiszpo])
def sajat_diszpok(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """A bejelentkezett munkatárs SAJÁT diszpói (amiknek a stábjában benne
    van), dátum szerint csökkenő sorrendben. Nincs oldal-jogosultsághoz kötve:
    mindenki a saját diszpóit látja, mást nem."""
    projektek = (
        db.query(Project)
        .filter(Project.crew.any(Employee.id == current_user.id))
        .order_by(Project.forgatas_datuma.desc().nulls_last(), Project.id.desc())
        .limit(500)
        .all()
    )
    return [
        SajatDiszpo(
            project_id=p.id,
            projekt_nev=p.nev,
            forgatas_datuma=p.forgatas_datuma,
            forgatas_vege=(
                p.forgatas_datuma_vege
                or getattr(p, "naptar_datum_vege", None)
                or getattr(p, "notion_datum_vege", None)
            ),
            pdf_url=p.drive_diszpo_pdf_url or p.diszpo_pdf_url,
        )
        for p in projektek
    ]


@router.get("/my-tasks", response_model=MyTasksSummary)
def my_tasks(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """A "Teendőim" dashboard-widget adatai - a bejelentkezett felhasználóra
    kiosztott, még nyitott Utómunkák és Feladatok, hogy egy helyen lássa, mivel
    kell foglalkoznia."""
    # Ami ELKÉSZÜLT állapotban van, az akkor sem teendő, ha még nincs
    # kiküldve - ugyanaz a szabály, mint a lejárt-határidő számlálónál (lásd
    # summary): melyik állapot számít késznek, azt az admin állítja be az
    # Utómunka tábláján (models/deliverable_status.py).
    kesz_allapotok = list(
        db.scalars(
            select(DeliverableStatusConfig.allapot).where(DeliverableStatusConfig.kesz_allapot.is_(True))
        ).all()
    )
    # Amely állapothoz AUTOMATIKUS kiosztás tartozik, és ebben a felhasználó
    # benne van (pl. "Kiküldésre vár" -> akik kiküldik), az az állapot NEKI
    # akkor is teendő, ha egyébként "kész"-nek számít: pont ott van vele
    # dolga (a felhasználó kérése - a dashboardon is jelenjen meg).
    auto_allapotok = [
        sor.allapot
        for sor in db.scalars(
            select(DeliverableStatusConfig).where(DeliverableStatusConfig.auto_kiosztott_employee_ids.is_not(None))
        ).all()
        if current_user.id in [int(i) for i in (sor.auto_kiosztott_employee_ids or [])]
    ]
    nyitott_feltetelek = [
        # Több embert is ki lehet osztani egy anyagra (kiosztottak m2m) - a
        # régi egyértékű mezőt is nézzük, hátha egy régi író csak azt tölti.
        or_(
            Deliverable.kiosztottak.any(Employee.id == current_user.id),
            Deliverable.assigned_to_employee_id == current_user.id,
        ),
        Deliverable.anyag_kikuldve.is_(False),
    ]
    if kesz_allapotok:
        allapot_feltetelek = [Deliverable.allapot.is_(None), Deliverable.allapot.not_in(kesz_allapotok)]
        if auto_allapotok:
            allapot_feltetelek.append(Deliverable.allapot.in_(auto_allapotok))
        nyitott_feltetelek.append(or_(*allapot_feltetelek))
    deliverables = db.scalars(
        select(Deliverable).where(*nyitott_feltetelek).order_by(Deliverable.hatarido.asc().nulls_last())
    ).all()
    tasks = db.scalars(
        select(Task)
        .join(task_employees, task_employees.c.task_id == Task.id)
        .where(task_employees.c.employee_id == current_user.id, Task.checked.is_(False))
        .order_by(Task.hatarido.asc().nulls_last())
    ).all()
    # A rád osztott AUTÓ-TEENDŐK - a rendszám mondja meg, melyik kocsiról van
    # szó (lásd models/auto.AutoTeendo).
    auto_teendok = db.execute(
        select(AutoTeendo, Auto.rendszam)
        .join(Auto, Auto.id == AutoTeendo.auto_id)
        .where(AutoTeendo.felelos_id == current_user.id, AutoTeendo.kesz.is_(False))
        .order_by(AutoTeendo.hatarido.asc().nulls_last())
    ).all()

    # A HYPE TO-DO feladataid, amíg nincsenek készre téve ("Done").
    hype_todok = db.scalars(
        select(HypeTodoItem)
        .join(hype_todo_felelosok, hype_todo_felelosok.c.hype_todo_id == HypeTodoItem.id)
        .where(
            hype_todo_felelosok.c.employee_id == current_user.id,
            or_(HypeTodoItem.allapot.is_(None), HypeTodoItem.allapot != "Done"),
        )
        .order_by(HypeTodoItem.hatarido.asc().nulls_last())
    ).all()

    return MyTasksSummary(
        deliverables=[
            MyTaskItem(
                id=d.id,
                # Az állapot-alapú (automatikus) teendőnél a cím az ÁLLAPOTOT
                # is mondja - abból derül ki, MIÉRT teendő ("Kiküldésre vár").
                title=(d.projekt_neve or f"Anyag #{d.id}")
                + (f" – {d.allapot}" if d.allapot and d.allapot in auto_allapotok else ""),
                hatarido=d.hatarido,
                link=f"/utomunka/{d.id}",
            )
            for d in deliverables
        ],
        tasks=[MyTaskItem(id=t.id, title=t.feladat, hatarido=t.hatarido, link="/feladatok") for t in tasks],
        auto_teendok=[
            MyTaskItem(id=t.id, title=f"{rendszam}: {t.szoveg}", hatarido=t.hatarido, link="/autok")
            for t, rendszam in auto_teendok
        ],
        hype_todok=[
            MyTaskItem(id=h.id, title=h.feladat, hatarido=h.hatarido, link=f"/hype-todo-lista/{h.id}")
            for h in hype_todok
        ],
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
    if not van_szerepkore(user, SystemRole.ADMINISZTRACIO):
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

    # 3. Megrendelői szerződés és TIG - projektkódonként, a papírok VALÓDI
    #    állapotából (lásd services/megrendeloi_papir.py). A kihagyott és a
    #    "van már papír" jelölésű tételek lezártnak számítanak: azok nem
    #    elmaradtak, hanem eldőltek.
    projektkodok = list(db.scalars(select(ProjectCode).order_by(ProjectCode.projektkod)))
    allasok = megrendeloi_papir.papir_allasok(db, projektkodok)
    for pc in projektkodok:
        # A papírozásból kivett sorozatok (HYPE24) papírjai máshol készültek el -
        # nincs velük teendő (lásd services/papirozas_hatokor.py).
        if papirozas_hatokor.projektkod_kivett(pc.projektkod):
            continue
        allas = allasok[pc.id]
        # A projektkód kapcsolói kivehetik a papírozásból: nincs szerződés a
        # projekt mögött, vagy papír nélkül számoljuk el. Ilyenkor nem "hiányzik"
        # a papír, hanem nincs is neki helye.
        if not allas.kell_papir:
            continue
        # Élő keretszerződés alatt nincs eseti szerződés-teendő: a keret fedi a
        # munkát (lásd services/megrendeloi_papir.PapirAllas.szerzodes_kell).
        if allas.szerzodes_kell and not allas.szerzodes_kesz:
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
        # Csak a RENDSZER-ÉRA kiküldött diszpói jelentenek TIG-teendőt: a
        # régebbi forgatások "Kiküldve" jelölése visszamenőleges adatpótlás
        # (lásd services/papirozas_hatokor.rendszer_kezdete).
        if not allas.tig_kesz and any(papirozas_hatokor.rendszer_diszpozott(p) for p in pc.projects):
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
        # A kitörölhetetlen nyom is számít (lásd models/project.py
        # diszpo_kikuldve_at) - egy külső folyamat által kiürített szöveges
        # mező ne gyártson hamis "küldd ki a diszpót" teendőt.
        teljes_kiment = bool(p.diszpo or p.diszpo_kikuldve_at)
        elozetes_kiment = bool(p.elozetes_diszpo_kuldes or p.elozetes_kikuldve_at)
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
