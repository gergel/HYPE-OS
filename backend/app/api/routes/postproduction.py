"""Utómunka modul: Deliverable (vágandó anyag) + Timesheet (ledolgozott idő) + Feedback (gombos visszajelzés)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import (
    Role,
    ellenorizd_anyag_hozzaferest,
    get_current_user,
    lathato_anyagok,
    require_page_action,
    require_roles,
)
from app.models.deliverable import Deliverable
from app.models.deliverable_status import DeliverableBoardConfig, DeliverableStatusConfig
from app.models.employee import Employee
from app.models.feedback import Feedback
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.schemas.deliverable import DeliverableCreate, DeliverableListItem, DeliverableRead, DeliverableUpdate
from app.schemas.deliverable_actions import (
    AssignableEmployee,
    CommentCreate,
    CommentRead,
    ContactIdsPayload,
    ContactOption,
    TimerState,
    VinyoOptions,
)
from app.schemas.feedback import FeedbackCreate, FeedbackRead, FeedbackUpdate
from app.schemas.timesheet import TimesheetCreate, TimesheetRead, TimesheetUpdate
from app.services import deliverable_actions, notifications, projektkod_kotes, vagoi_jatek


def _after_deliverable_update(
    obj: Deliverable, data: dict, m2m_changes: dict, db: Session, current_user: Employee
) -> None:
    """A PATCH utáni mellékhatások: kiosztás-értesítés és a vágói játék pontja."""
    # Ellenőrzésbe került az anyag -> a vágói játékban pont jár érte annak, aki
    # odatette (lásd services/vagoi_jatek.py). Idempotens: ugyanaz az anyag
    # akkor sem hoz még egyszer pontot, ha kiveszik és visszateszik.
    if "allapot" in data and vagoi_jatek.ellenorzes_allapot(obj.allapot):
        if vagoi_jatek.rogzitsd_ellenorzest(db, obj, current_user):
            db.commit()

    # Kiosztás (Assigned To) -> értesítés a munkatársnak, lásd AssignedToPicker.tsx.
    if "assigned_to_employee_id" not in data:
        return
    new_id = data["assigned_to_employee_id"]
    if not new_id:
        return
    title = obj.projekt_neve or f"Anyag #{obj.id}"
    notifications.create_notification(
        db,
        employee_id=new_id,
        kind="assignment",
        message=f"{current_user.full_name} kiosztotta neked: {title}",
        link=f"/utomunka/{obj.id}",
        actor_id=current_user.id,
    )
    db.commit()


def _csak_a_sajat_anyagai(stmt, db: Session, user: Employee):
    """Sorszűrő a korlátozott fiókokhoz: egy külsős vágó csak azt az anyagot
    látja, amire behívtuk (lásd core/security.lathato_anyagok). Aki nincs
    korlátozva, annak a lekérdezés változatlan."""
    engedett = lathato_anyagok(db, user)
    if engedett is None:
        return stmt
    return stmt.where(Deliverable.id.in_(engedett or {0}))


def _vagas_projektkodja(data: dict, db: Session) -> dict:
    """Új vágásnál KÖTELEZŐ a projektkód - és ha projekthez vesszük fel, akkor
    a projektét örökli.

    Miért kötelező: a vágás a projektkód alá tartozik (abból derül ki, melyik
    munka utómunkája, és ott számol a költsége). Kód nélkül felvéve viszont
    csak egy cím marad a listán, amit később senki nem tud besorolni - és
    pontosan ezek gyűltek fel eddig.

    A formátum SZABAD: nem minden munka a megszokott kód-alakot viseli (más
    ügyfél rendszere, régi sorozat). Csak azt kérjük, hogy legyen kód, és ne
    az import gyűjtője legyen (lásd services/projektkod_kotes.py)."""
    projekt = db.get(Project, data["project_id"]) if data.get("project_id") else None
    if projekt is not None and not (data.get("projektkod_szoveg") or "").strip():
        # Projekthez felvezetett vágás: a projekt kódját örökli.
        data["projektkod_szoveg"] = projekt.projektkod_szoveg
        if not data.get("project_code_id"):
            data["project_code_id"] = projekt.project_code_id

    kod = (data.get("projektkod_szoveg") or "").strip()
    if not projektkod_kotes.valodi(kod):
        raise HTTPException(
            status_code=400,
            detail=(
                "A vágáshoz meg kell adni a projektkódot. Ebből derül ki, melyik munka "
                "utómunkája, és ez alapján kerül a helyére a projektkód adatlapján. A "
                "formátum szabad - bármilyen kód megadható, csak ne maradjon üresen."
                if not kod
                else "Az import gyűjtő kódja nem valódi projektkód - add meg a munka saját kódját."
            ),
        )
    data["projektkod_szoveg"] = kod
    # A szöveghez tartozó Project Code-ot magunk keressük meg: így a vágás
    # rögtön a helyére kerül, nem kell utólag összekötni.
    if not data.get("project_code_id"):
        talalat = projektkod_kotes.keresd(db, kod)
        if talalat is not None:
            data["project_code_id"] = talalat.id
    return data


#: A frontend ebből a PONTOS szövegből ismeri fel ezt a konkrét hibát (lásd
#: UtomunkaContent.allapotAtallitasa) - nem egyeznél, a sima hiba-alert
#: futna a felugró visszajelzés-űrlap helyett.
VISSZAJELZES_HIANYZIK_UZENET = "Mielőtt ellenőrzésbe teszed, írj visszajelzést ehhez az anyaghoz."


def _ellenorzeshez_kell_visszajelzes(obj: Deliverable, data: dict, db: Session, current_user: Employee) -> None:
    """Csak az teheti ellenőrzésbe az anyagot, aki már ÍRT hozzá vágói
    visszajelzést (lásd models/feedback.py).

    A visszajelzés a nyersanyagról szól a gyártásnak (mit kapott a vágó, min
    lehetne javítani) - enélkül könnyen elmarad, mert semmi nem kényszeríti
    ki: az anyag ugyanúgy "kész"/"ellenőrzésbe" tehető visszajelzés nélkül is,
    és a vágó a következő munkára ugrik. Nem kell ÚJ visszajelzést írni ehhez
    a konkrét pillanathoz - ha valamikor korábban már írt egyet erre az
    anyagra, azzal a feltétel teljesül."""
    if "allapot" not in data or not vagoi_jatek.ellenorzes_allapot(data.get("allapot")):
        return
    van_visszajelzese = (
        db.scalar(
            select(Feedback.id).where(
                Feedback.deliverable_id == obj.id,
                Feedback.visszajelzo_employee_id == current_user.id,
            )
        )
        is not None
    )
    if not van_visszajelzese:
        # SIMA SZÖVEG a detail - nem strukturált objektum: kb. 80 helyen fut
        # a felületen ugyanaz a minta (`alert(\`...: ${detail?.detail}\`)`),
        # ami stringnek várja - egy objektum "[object Object]"-ként jelenne
        # meg mindenhol máshol, ahol ezt a hibát esetleg elkapják (pl. a
        # generikus EditableDetailGrid, amivel BÁRMELYIK entitás BÁRMELYik
        # mezője szerkeszthető). A SZÖVEG maga a kapocs a felugró
        # visszajelzés-űrlaphoz (lásd UtomunkaContent.allapotAtallitasa) -
        # ha itt átírod, ott is át kell.
        raise HTTPException(
            status_code=400,
            detail=VISSZAJELZES_HIANYZIK_UZENET,
        )


def _kovesd_a_vagas_projektkodjat(obj: Deliverable, data: dict, db: Session, current_user: Employee) -> None:
    """A Deliverable PATCH-ének before_update ellenőrzései - csak EGY hívás
    kapcsolható a routerre, ezért ez fogja össze az önálló szabályokat.

    Elsőként: aki ellenőrzésbe teszi az anyagot, annak van-e már visszajelzése
    hozzá (lásd _ellenorzeshez_kell_visszajelzes). Utána: ha átírják a vágás
    projektkódját, kövesse a kötés is - és ne lehessen kiüríteni: a vágásnak
    MINDIG van kódja (lásd _vagas_projektkodja)."""
    _ellenorzeshez_kell_visszajelzes(obj, data, db, current_user)
    if "projektkod_szoveg" not in data:
        return
    kod = (data.get("projektkod_szoveg") or "").strip()
    if not projektkod_kotes.valodi(kod):
        raise HTTPException(
            status_code=400,
            detail="A vágás projektkódja nem törölhető - a vágás a projektkód alá tartozik.",
        )
    talalat = projektkod_kotes.keresd(db, kod)
    if talalat is not None:
        obj.project_code_id = talalat.id


deliverables_router = build_crud_router(
    model=Deliverable,
    create_schema=DeliverableCreate,
    update_schema=DeliverableUpdate,
    read_schema=DeliverableRead,
    list_read_schema=DeliverableListItem,
    prefix="/deliverables",
    tags=["postproduction"],
    page="/utomunka",
    before_create=_vagas_projektkodja,
    before_update=_kovesd_a_vagas_projektkodjat,
    after_update=_after_deliverable_update,
    entity_type="deliverable",
    sor_szuro=_csak_a_sajat_anyagai,
)

timesheets_router = build_crud_router(
    model=Timesheet,
    create_schema=TimesheetCreate,
    update_schema=TimesheetUpdate,
    read_schema=TimesheetRead,
    prefix="/timesheets",
    tags=["postproduction"],
    page="/utomunka",
)

feedback_router = build_crud_router(
    model=Feedback,
    create_schema=FeedbackCreate,
    update_schema=FeedbackUpdate,
    read_schema=FeedbackRead,
    prefix="/feedback",
    tags=["postproduction"],
    page="/utomunka",
)

# Külön router a Deliverable egyedi (nem CRUD) akcióihoz - FONTOS: ezt kell
# ELŐBB regisztrálni (lásd routes/__init__.py), mint a fenti deliverables_router-t,
# mert a generikus GET/PATCH/DELETE "/deliverables/{item_id}" route egyébként
# lenyelné az olyan statikus útvonalakat, mint "/deliverables/assignable-employees"
# (FastAPI/Starlette regisztrációs sorrendben próbálja a route-okat).
deliverable_actions_router = APIRouter(prefix="/deliverables", tags=["postproduction"])


def _get_deliverable_or_404(deliverable_id: int, db: Session, user: Employee | None = None) -> Deliverable:
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utómunka nem található")
    if user is not None:
        # A korlátozott fiók (külsős vágó) csak a saját anyagán dolgozhat -
        # az akció-végpontokra ugyanaz a szűkítés vonatkozik, mint a listára.
        ellenorizd_anyag_hozzaferest(db, user, deliverable_id)
    return deliverable


@deliverable_actions_router.get("/assignable-employees", response_model=list[AssignableEmployee])
def get_assignable_employees(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Kik jelölhetők ki az "Assigned To" mezőben - csak azok, akiknek van
    bejelentkezési joga és hozzáférése az /utomunka oldalhoz."""
    return deliverable_actions.list_assignable_employees(db)


class AllapotBeallitas(BaseModel):
    """Egy utómunka-állapot megjelenése a táblán."""

    allapot: str
    sorrend: int = 0
    #: "#rrggbb" vagy üres - az oszlop (és a kártyái) halvány színe.
    szin: str | None = None
    #: Elkészültnek számít-e (ilyenkor nem lesz belőle lejárt határidő).
    kesz_allapot: bool = False

    model_config = {"from_attributes": True}


class AllapotBeallitasokIn(BaseModel):
    beallitasok: list[AllapotBeallitas]


@deliverable_actions_router.get("/allapot-beallitasok", response_model=list[AllapotBeallitas])
def get_allapot_beallitasok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az utómunka-állapotok megjelenése: sorrend, szín, és hogy melyik számít
    elkészültnek (lásd models/deliverable_status.py)."""
    sorok = db.query(DeliverableStatusConfig).order_by(DeliverableStatusConfig.sorrend, DeliverableStatusConfig.id).all()
    return [AllapotBeallitas.model_validate(s) for s in sorok]


@deliverable_actions_router.put("/allapot-beallitasok", response_model=list[AllapotBeallitas])
def set_allapot_beallitasok(
    payload: AllapotBeallitasokIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/utomunka", "edit")),
):
    """A teljes beállítás-lista cseréje (a felület mindig az egészet küldi).

    A sorrendet a lista SORRENDJE adja, nem a beküldött szám - így a felületen
    elég fel/le mozgatni a sorokat, nem kell indexeket számolgatni."""
    meglevo = {s.allapot: s for s in db.query(DeliverableStatusConfig).all()}
    kuldott: set[str] = set()
    for index, elem in enumerate(payload.beallitasok):
        allapot = (elem.allapot or "").strip()
        if not allapot:
            continue
        kuldott.add(allapot)
        sor = meglevo.get(allapot)
        if sor is None:
            sor = DeliverableStatusConfig(allapot=allapot)
            db.add(sor)
        sor.sorrend = index
        sor.szin = (elem.szin or "").strip() or None
        sor.kesz_allapot = elem.kesz_allapot
    # Amit a felület nem küldött vissza, az már nem választható állapot -
    # a beállítása is elévült.
    for allapot, sor in meglevo.items():
        if allapot not in kuldott:
            db.delete(sor)
    db.commit()
    return get_allapot_beallitasok(db)


class KartyaMezokIn(BaseModel):
    kartya_mezok: list[str]


class KartyaMezok(BaseModel):
    """Mely mezők jelenjenek meg a tábla kártyáin (üres = alapértelmezés)."""

    kartya_mezok: list[str] = []


def _board_config(db: Session) -> DeliverableBoardConfig:
    """A tábla egyetlen beállítás-sora - ha még nincs, létrehozzuk."""
    config = db.query(DeliverableBoardConfig).order_by(DeliverableBoardConfig.id).first()
    if config is None:
        config = DeliverableBoardConfig()
        db.add(config)
        db.flush()
    return config


@deliverable_actions_router.get("/kartya-mezok", response_model=KartyaMezok)
def get_kartya_mezok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Mely adatok látszódjanak a Vágó nézet kártyáin (lásd
    models/deliverable_status.py DeliverableBoardConfig)."""
    config = db.query(DeliverableBoardConfig).order_by(DeliverableBoardConfig.id).first()
    return KartyaMezok(kartya_mezok=list(config.kartya_mezok or []) if config else [])


@deliverable_actions_router.put("/kartya-mezok", response_model=KartyaMezok)
def set_kartya_mezok(
    payload: KartyaMezokIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/utomunka", "edit")),
):
    config = _board_config(db)
    # Csak valódi Deliverable-oszlopokat fogadunk el: a kártya generikusan
    # olvassa ki az értéket, egy elgépelt mezőnév csak üres sort adna.
    mezok = [m for m in payload.kartya_mezok if m in Deliverable.__table__.columns]
    config.kartya_mezok = mezok or None
    db.commit()
    return KartyaMezok(kartya_mezok=mezok)


@deliverable_actions_router.get("/vinyo-options", response_model=VinyoOptions)
def get_vinyo_options(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A valaha használt vinyó-értékek egyesített listája (choose-from lista a
    "Vinyók" többválasztós mezőhöz)."""
    return deliverable_actions.get_vinyo_options(db)


@deliverable_actions_router.get("/{deliverable_id}/contacts", response_model=list[ContactOption])
def get_deliverable_contacts(
    deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)
):
    return deliverable_actions.list_contacts(_get_deliverable_or_404(deliverable_id, db, current_user))


@deliverable_actions_router.put("/{deliverable_id}/contacts", response_model=list[ContactOption])
def set_deliverable_contacts(
    deliverable_id: int,
    payload: ContactIdsPayload,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Lecseréli a "Megrendelői kontaktok" listát, és újraszámolja a
    megrendeloi_email_cimek formula-mezőt."""
    deliverable = deliverable_actions.set_contacts(db, _get_deliverable_or_404(deliverable_id, db, current_user), payload.contact_ids)
    return deliverable_actions.list_contacts(deliverable)


@deliverable_actions_router.post("/{deliverable_id}/timer/start", status_code=status.HTTP_204_NO_CONTENT)
def start_timer(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    try:
        deliverable_actions.start_timer(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@deliverable_actions_router.post("/{deliverable_id}/timer/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_timer(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    try:
        deliverable_actions.stop_timer(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@deliverable_actions_router.post(
    "/{deliverable_id}/timer/stop/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def stop_timer_for_employee(
    deliverable_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """MÁS ember futó időmérésének leállítása - csak adminnak. Egy elfelejtett
    mérőt egyébként csak az tudna lezárni, aki elindította; ha ő nincs gépnél,
    egész éjjel futna (és a belőle számolt költség is hibás lenne)."""
    try:
        deliverable_actions.stop_timer(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@deliverable_actions_router.get("/{deliverable_id}/timer/state", response_model=TimerState)
def get_timer_state(deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    return deliverable_actions.get_timer_state(db, _get_deliverable_or_404(deliverable_id, db, current_user), current_user)


class VisszajelzesIn(BaseModel):
    """A vágói visszajelzés űrlapja: három pontszám (1-10) és a megjegyzés."""

    nyersanyag_felhasznalhatosaga: float | None = None
    technikai_helyesseg: float | None = None
    kreativ_kepivilag: float | None = None
    megjegyzes: str | None = None


@deliverable_actions_router.post("/{deliverable_id}/visszajelzes", response_model=FeedbackRead)
def send_visszajelzes(
    deliverable_id: int,
    payload: VisszajelzesIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """A vágói visszajelzés rögzítése az űrlapról - lásd
    services/deliverable_actions.send_visszajelzes."""
    try:
        return deliverable_actions.send_visszajelzes(
            db,
            _get_deliverable_or_404(deliverable_id, db, current_user),
            current_user,
            nyersanyag_felhasznalhatosaga=payload.nyersanyag_felhasznalhatosaga,
            technikai_helyesseg=payload.technikai_helyesseg,
            kreativ_kepivilag=payload.kreativ_kepivilag,
            megjegyzes=payload.megjegyzes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


class PercekIn(BaseModel):
    """Percek egy már rögzített munkaidő-sorra - lásd set_timesheet_minutes."""

    minutes: float


@deliverable_actions_router.post("/{deliverable_id}/timesheets/{timesheet_id}/percek", response_model=TimesheetRead)
def set_timesheet_minutes(
    deliverable_id: int,
    timesheet_id: int,
    payload: PercekIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/utomunka", "edit")),
):
    """Egy munkaidő-sor percének UTÓLAGOS javítása - ha valaki elfelejtette
    leállítani az időmérőt (pl. egész éjjel futott), ez az egyetlen módja, hogy
    a valós munkaidő kerüljön be. A költséget is újraszámoljuk az akkori
    órabérrel, különben a Pénzügyben a hibás összeg maradna."""
    if payload.minutes < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A perc nem lehet negatív.")
    row = db.get(Timesheet, timesheet_id)
    if row is None or row.deliverable_id != deliverable_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen munkaidő-elszámolás ezen az anyagon.")
    row.time_minutes = payload.minutes
    # Az órabér a sor SAJÁT, befagyasztott órabére (akkori_orabere) - egy
    # későbbi béremelés a régi költséget nem írhatja át. Ha még nincs rögzítve,
    # most vesszük fel a mostanit.
    if row.akkori_orabere is None:
        row.akkori_orabere = deliverable_actions.aktualis_orabere(db, row.employee_id)
    row.koltseg = deliverable_actions.szamolt_koltseg(payload.minutes, row.akkori_orabere)
    db.commit()
    db.refresh(row)
    return row


@deliverable_actions_router.get("/{deliverable_id}/comments", response_model=list[CommentRead])
def get_comments(
    deliverable_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)
):
    _get_deliverable_or_404(deliverable_id, db, current_user)
    return deliverable_actions.list_comments(db, deliverable_id)


@deliverable_actions_router.post("/{deliverable_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def post_comment(
    deliverable_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    _get_deliverable_or_404(deliverable_id, db, current_user)
    if not payload.body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A hozzászólás nem lehet üres")
    return deliverable_actions.add_comment(db, deliverable_id, current_user, payload.body.strip())
