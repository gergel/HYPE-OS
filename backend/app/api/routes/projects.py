from datetime import datetime

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, get_current_user, require_page_action, require_roles
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.project import Project
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.timesheet import Timesheet
from app.schemas.deliverable import DeliverableRead
from app.schemas.deliverable_actions import TimerEmployeeSummary
from app.schemas.project import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate, SzerzodesKeszitesPayload
from app.services import deliverable_actions, projektkod_kotes
from app.services.contract_actions import apply_szerzodes_keszites, send_szerzodes
from app.services.dispo import send_diszpo, send_elozetes_diszpo
from app.services.project_actions import DarabolasHiba, create_feldarabolas, create_utomunka
from app.services.technika import check_technika

def _block_delete_if_portal_content(project: Project, _db: Session) -> None:
    """A projekt saját rekordjai (eszközfoglalás, diszpó-adatlap, szerződések,
    TIG-ek, utómunkák) a projekttel együtt törlődnek (lásd models/project.py
    cascade-jei), a Média Portál tartalma viszont NEM: az ügyfélnek kiadott,
    akár már kifizetett anyag, amit nem szabad egy projekt-törlés
    mellékhatásaként elveszíteni. Ilyenkor inkább érthető hibaüzenettel
    elutasítjuk a törlést, hogy a felhasználó tudatosan dönthessen."""
    blockers = []
    if project.portal is not None:
        blockers.append("Média Portál")
    if project.media_items:
        blockers.append(f"{len(project.media_items)} médiafájl")
    if project.folders:
        blockers.append(f"{len(project.folders)} mappa")
    if blockers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A projekt nem törölhető, mert tartozik hozzá "
                + ", ".join(blockers)
                + ". Ezeket a Média Portál oldalon kell előbb törölni - "
                "szándékosan nem töröljük őket a projekttel együtt."
            ),
        )


def _takaritsd_a_szamlazokat(
    project: Project, _data: dict, m2m_changes: dict[str, dict[str, set[int]]], db: Session, _user: Employee
) -> None:
    """Aki lekerült a stáblistáról, annak a számlázó-beállítása is menjen vele.

    Kétféle irányban: a levett ember SAJÁT beállítása fölöslegessé válik, és ha
    ő volt más(ok) számlázója, azok a sorok is hazuggá válnának - egy olyan
    embert neveznének meg, aki már nincs a projekten (lásd
    models/project_szamlazo.py)."""
    eltavolitott = m2m_changes.get("crew", {}).get("removed") or set()
    if not eltavolitott:
        return
    (
        db.query(ProjectSzamlazo)
        .filter(
            ProjectSzamlazo.project_id == project.id,
            or_(
                ProjectSzamlazo.employee_id.in_(eltavolitott),
                ProjectSzamlazo.szamlazo_employee_id.in_(eltavolitott),
            ),
        )
        .delete(synchronize_session=False)
    )
    db.commit()


def _kosd_a_projektkodhoz(data: dict, db: Session) -> dict:
    """Új projektnél: ha van projektkód-szöveg, keressük meg hozzá a Project
    Code-ot. Így a projekt rögtön a helyére kerül, nem kell utólag összekötni
    (lásd services/projektkod_kotes.py).

    A projektkód itt NEM kötelező: a naptárból érkező eseménynek még nincs, és
    a felvitel pillanatában sem mindig ismert. A kapunál (diszpó kiküldés) kell
    meglennie - addig a projekt kód nélkül is létezhet, csak nem lehet
    kiküldeni róla semmit."""
    kod = (data.get("projektkod_szoveg") or "").strip()
    if kod and not data.get("project_code_id"):
        talalat = projektkod_kotes.keresd(db, kod)
        if talalat is not None:
            data["project_code_id"] = talalat.id
    return data


def _kovesd_a_projektkod_valtozast(obj: Project, data: dict, db: Session, _current_user: Employee) -> None:
    """Ha valaki átírja a projektkód SZÖVEGÉT, kövesse a kötés is.

    Enélkül a projekt a régi Project Code alatt maradna - és a projektkód
    adatlapja rossz forgatásokat sorolna fel."""
    if "projektkod_szoveg" not in data:
        return
    talalat = projektkod_kotes.keresd(db, data.get("projektkod_szoveg"))
    if talalat is not None:
        obj.project_code_id = talalat.id


router = build_crud_router(
    model=Project,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    read_schema=ProjectRead,
    list_read_schema=ProjectListItem,
    prefix="/projects",
    tags=["projects"],
    page="/projektek",
    m2m_fields={"crew_employee_ids": ("crew", Employee)},
    before_create=_kosd_a_projektkodhoz,
    before_update=_kovesd_a_projektkod_valtozast,
    after_update=_takaritsd_a_szamlazokat,
    before_delete=_block_delete_if_portal_content,
    entity_type="project",
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")
    return project


@router.post(
    "/{project_id}/technika-check",
    tags=["projects"],
    # A gomb a projektre ír vissza (technika_lista, backend_statusz), tehát a
    # projekt szerkesztési joga kell hozzá - a diszpós ezt aliaszon át megkapja
    # (lásd core/security.OLDAL_ALIASZOK), egy máshova korlátozott operátor nem.
    dependencies=[Depends(require_page_action("/projektek", "edit", Role.ADMIN, Role.OPERATOR))],
)
def run_technika_check(project_id: int, db: Session = Depends(get_db)):
    """A 'Technika ready' gomb - lefuttatja az eszköz-ütközés ellenőrzést a
    projekthez rendelt (Assignment) eszközökre, és visszaírja az eredményt
    (technika_lista, backend_statusz, backend_uzenet)."""
    return check_technika(db, _get_project_or_404(project_id, db))


@router.post("/{project_id}/feldarabolas", response_model=ProjectRead, tags=["projects"])
def run_feldarabolas(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN, Role.OPERATOR))):
    """A 'Feldarabolás' gomb - új Project sort hoz létre ugyanahhoz a Project
    Code-hoz, átmásolva a nevet/leírást/projektkódot/stábot (lásd
    app/services/project_actions.py)."""
    try:
        return create_feldarabolas(db, _get_project_or_404(project_id, db))
    except DarabolasHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/create-utomunka", response_model=DeliverableRead, tags=["projects"])
def run_create_utomunka(
    project_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(require_roles(Role.ADMIN, Role.OPERATOR))
):
    """Az 'Utómunka' gomb - új Deliverable-t hoz létre ehhez a projekthez, a Notion
    automatizmussal megegyező névképzéssel (lásd app/services/project_actions.py)."""
    return create_utomunka(db, _get_project_or_404(project_id, db), current_user)


def _run_dispatch_action(action, *args):
    """A diszpó/szerződés küldő akciók (Gmail/Google Docs hívást igényelnek) közös
    hibakezelése: ValueError -> 400 (pl. hiányzó címzett), RuntimeError -> 503
    (hiányzó Google hitelesítő adat - csak Railway-en, valódi env varokkal
    tesztelhető, lásd app/services/google_email.py)."""
    try:
        return action(*args)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


#: A két diszpó-küldő gomb jogosultsága. SZÁNDÉKOSAN oldal+művelet alapú, nem
#: puszta szerepkör: így egyrészt a "csak diszpó" hozzáférésű munkatárs is ki
#: tudja küldeni (a /naptar joga a /projektek "edit"-jét is megadja, lásd
#: core/security.OLDAL_ALIASZOK), másrészt egy máshova korlátozott operátor
#: NEM - korábban bármelyik operátor kiküldhetett bármilyen diszpót, akkor is,
#: ha a Projektek oldalhoz nem is volt joga.
_diszpo_kuldheti = require_page_action("/projektek", "edit", Role.ADMIN, Role.OPERATOR)


@router.post("/{project_id}/diszpo/elozetes", tags=["projects"])
def run_elozetes_diszpo(
    project_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(_diszpo_kuldheti)
):
    """'Előzetes diszpó' gomb (lásd app/services/dispo.py)."""
    return _run_dispatch_action(send_elozetes_diszpo, db, _get_project_or_404(project_id, db), current_user)


@router.post("/{project_id}/diszpo/kuldes", tags=["projects"])
def run_diszpo_kuldes(
    project_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(_diszpo_kuldheti)
):
    """'Diszpó küldése' gomb (lásd app/services/dispo.py)."""
    return _run_dispatch_action(send_diszpo, db, _get_project_or_404(project_id, db), current_user)


@router.post(
    "/{project_id}/szerzodes-keszites",
    response_model=ProjectRead,
    tags=["projects"],
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def run_szerzodes_keszites(project_id: int, payload: SzerzodesKeszitesPayload, db: Session = Depends(get_db)):
    """'Szerződés készítés' relation (Külsős és belsős) - a kiválasztott ember adatai
    a Project megbízott_* mezőibe másolódnak (lásd app/services/contract_actions.py)."""
    try:
        return apply_szerzodes_keszites(db, _get_project_or_404(project_id, db), payload.employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{project_id}/szerzodes-keszites-es-kuldese",
    tags=["projects"],
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def run_szerzodes_kuldes(project_id: int, db: Session = Depends(get_db)):
    """'szerződés készítése és küldése' gomb (lásd app/services/contract_actions.py)."""
    return _run_dispatch_action(send_szerzodes, db, _get_project_or_404(project_id, db))


class UtomunkaFuto(BaseModel):
    """Egy ÉPP FUTÓ mérés a projekt anyagain - a felület ebből számolja
    másodpercenként tovább az időt és a költséget."""

    since: datetime
    orabere: float | None = None


class ProjektUtomunkaOsszesites(BaseModel):
    """A projekt összes utómunka-ideje és -költsége, KI-re bontva.

    Azért a szerver adja (és nem a felület adja össze a nyers sorokból), mert
    a költség sokszor nincs rögzítve a soron (a Notionból hozott méréseknél
    jellemzően nincs) - ilyenkor az időből és az órabérből SZÁMOLJUK, ugyanazzal
    a szabállyal, mint az anyag oldalán (lásd deliverable_actions.sor_koltsege).
    Enélkül a projekten és az anyagon más összeg állna."""

    total_minutes: float = 0
    total_cost: float | None = None
    by_employee: list[TimerEmployeeSummary] = []
    futok: list[UtomunkaFuto] = []


@router.get("/{project_id}/utomunka-osszesites", response_model=ProjektUtomunkaOsszesites, tags=["projects"])
def utomunka_osszesites(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    rows = (
        db.query(Timesheet)
        .join(Deliverable, Timesheet.deliverable_id == Deliverable.id)
        .filter(Deliverable.project_id == project_id)
        .all()
    )
    lathat_koltseget = deliverable_actions._may_see_costs(db, current_user)

    percek: dict[int, float] = {}
    koltsegek: dict[int, float] = {}
    futok: list[UtomunkaFuto] = []
    gyorsito: dict[int, float | None] = {}
    for row in rows:
        if row.end_date is None and row.start_date is not None:
            futok.append(
                UtomunkaFuto(
                    since=row.start_date,
                    orabere=deliverable_actions.sor_orabere(db, row, gyorsito) if lathat_koltseget else None,
                )
            )
            continue
        percek[row.employee_id] = percek.get(row.employee_id, 0) + deliverable_actions.sor_percei(row)
        koltseg = deliverable_actions.sor_koltsege(db, row, gyorsito)
        if koltseg is not None:
            koltsegek[row.employee_id] = koltsegek.get(row.employee_id, 0) + koltseg

    nevek = (
        {e.id: e.full_name for e in db.query(Employee).filter(Employee.id.in_(percek.keys())).all()} if percek else {}
    )
    by_employee = sorted(
        (
            TimerEmployeeSummary(
                employee_id=eid,
                full_name=nevek.get(eid, "Ismeretlen"),
                total_minutes=perc,
                total_cost=koltsegek.get(eid) if lathat_koltseget else None,
            )
            for eid, perc in percek.items()
        ),
        key=lambda s: s.total_minutes,
        reverse=True,
    )
    return ProjektUtomunkaOsszesites(
        total_minutes=sum(percek.values()),
        total_cost=(sum(koltsegek.values()) if koltsegek else None) if lathat_koltseget else None,
        by_employee=by_employee,
        futok=futok,
    )
