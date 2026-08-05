import os
from datetime import datetime, timezone

from fastapi import Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, get_current_user, hash_password, require_page_action, require_roles
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.employee_document import EmployeeDocument
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.rate import Rate
from app.models.timesheet import Timesheet
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeDocumentRead,
    EmployeeRead,
    EmployeeUpdate,
    RateCreate,
    RateRead,
    RateUpdate,
)
from app.services import deliverable_actions, document_storage
from app.services.hu_datum import ev_honap_szoveg


def _hash_employee_password(data: dict, db: Session) -> dict:
    password = data.pop("password", None)
    if password:
        data["hashed_password"] = hash_password(password)
    return data


router = build_crud_router(
    model=Employee,
    create_schema=EmployeeCreate,
    update_schema=EmployeeUpdate,
    read_schema=EmployeeRead,
    prefix="/crew",
    tags=["crew"],
    page="/csapat",
    before_create=_hash_employee_password,
    entity_type="employee",
)


class SetPasswordPayload(BaseModel):
    password: str


@router.post(
    "/{employee_id}/set-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def set_employee_password(employee_id: int, payload: SetPasswordPayload, db: Session = Depends(get_db)):
    """Admin beállítja/visszaállítja egy meglévő munkatárs jelszavát - erre azért
    van szükség, mert a Notionből importált munkatársaknak sosem volt jelszavuk
    (hashed_password=None), tehát bejelentkezéshez valakinek adminként be kell
    állítania egyet nekik (lásd Beállítások oldal, per-felhasználó rész)."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A jelszónak legalább 6 karakter hosszúnak kell lennie")
    employee.hashed_password = hash_password(payload.password)
    db.commit()


class UtomunkaProjektIdo(BaseModel):
    """Egy vágó összesített utómunka-ideje EGY projekten, EGY hónapon belül."""

    project_id: int | None
    project_nev: str | None
    projektkod: str | None
    anyagok_szama: int
    total_minutes: float
    total_cost: float | None = None


class UtomunkaHonapIdo(BaseModel):
    """Egy HÓNAP összesítése: mennyit vágott a munkatárs, mennyibe került, és
    ezen belül projektenként hogyan oszlik meg."""

    ev: int
    honap: int
    honap_szoveg: str
    total_minutes: float
    total_cost: float | None = None
    projektek: list[UtomunkaProjektIdo] = []


class VagottAnyag(BaseModel):
    """Egy anyag, amin ez a vágó VALAHA dolgozott."""

    id: int
    projekt_neve: str
    allapot: str | None = None
    projektkod: str | None = None
    utoljara: datetime | None = None
    osszes_perc: float = 0


@router.get("/{employee_id}/vagott-anyagok", response_model=list[VagottAnyag])
def get_vagott_anyagok(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Minden anyag, amin ennek a munkatársnak VALAHA futott az időmérője -
    a legutóbb érintettel elöl.

    Szándékosan nem a Deliverable.vago_employee_id-t nézzük: az csak azt
    mondja meg, ki a jelenlegi kijelölt vágó. Egy anyagon többen is
    dolgozhattak, és a kijelölés utólag át is kerülhet másra - a tényleges
    munkát a munkaidő-sorok (Timesheet) őrzik."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")

    sorok = (
        db.query(Timesheet, Deliverable, ProjectCode)
        .join(Deliverable, Timesheet.deliverable_id == Deliverable.id)
        .outerjoin(ProjectCode, Deliverable.project_code_id == ProjectCode.id)
        .filter(Timesheet.employee_id == employee_id)
        .all()
    )

    anyagok: dict[int, VagottAnyag] = {}
    for timesheet, deliverable, projektkod in sorok:
        adat = anyagok.get(deliverable.id)
        if adat is None:
            adat = VagottAnyag(
                id=deliverable.id,
                projekt_neve=deliverable.projekt_neve,
                allapot=deliverable.allapot,
                projektkod=projektkod.projektkod if projektkod else None,
            )
            anyagok[deliverable.id] = adat
        adat.osszes_perc += float(timesheet.time_minutes or timesheet.idotartam_perc or 0)
        veg = timesheet.end_date or timesheet.start_date
        if veg is not None and (adat.utoljara is None or veg > adat.utoljara):
            adat.utoljara = veg

    # A legutóbb érintett anyag elöl; akinél nincs időpont, a lista végén.
    return sorted(
        anyagok.values(),
        key=lambda a: (a.utoljara is not None, a.utoljara or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )


@router.get("/{employee_id}/utomunka-ido", response_model=list[UtomunkaHonapIdo])
def get_utomunka_ido(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Mennyit vágott ez a munkatárs HÓNAPOKRA bontva, hónapon belül pedig
    projektenként - a személy adatlapján jelenik meg (lásd
    components/UtomunkaIdoHavonta.tsx). A projekt nélküli anyagok egy közös,
    "Projekt nélkül" sorba kerülnek (project_id=None).

    A hónapot a munka KEZDÉSE (start_date) dönti el. A még futó mérés is
    beleszámít, a mostani állásával - így a felületen látott összeg ugyanaz,
    mint az anyag oldalán ketyegő időmérőé.

    A forintos oszlop csak annak megy vissza, akinek a Pénzügy oldalhoz van
    hozzáférése (ugyanaz a szabály, mint az Utómunka oldalon - lásd
    services/deliverable_actions._may_see_costs)."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")

    rows = (
        db.query(Timesheet, Deliverable, Project)
        .join(Deliverable, Timesheet.deliverable_id == Deliverable.id)
        .outerjoin(Project, Deliverable.project_id == Project.id)
        .filter(Timesheet.employee_id == employee_id, Timesheet.start_date.isnot(None))
        .all()
    )

    lathat_koltseget = deliverable_actions._may_see_costs(db, current_user)
    most = datetime.now(timezone.utc)
    orabere_gyorsito: dict[int, float | None] = {}
    honapok: dict[tuple[int, int], UtomunkaHonapIdo] = {}
    projektek: dict[tuple[int, int], dict[int | None, UtomunkaProjektIdo]] = {}
    anyagok: dict[tuple[int, int, int | None], set[int]] = {}

    for timesheet, deliverable, project in rows:
        if timesheet.end_date is None:
            # Még fut: a mostani állásával számoljuk, hogy ne hiányozzon a
            # havi összesítésből, amíg valaki le nem állítja.
            percek = max(0.0, (most - timesheet.start_date).total_seconds() / 60)
            koltseg = deliverable_actions.szamolt_koltseg(
                percek, deliverable_actions.sor_orabere(db, timesheet, orabere_gyorsito)
            )
        else:
            percek = deliverable_actions.sor_percei(timesheet)
            # Rögzített összeg híján az időből és az órabérből számoljuk -
            # ugyanúgy, mint az anyag oldalán (lásd sor_koltsege), különben az
            # importált méréseknél üres maradna a forintos oszlop.
            koltseg = deliverable_actions.sor_koltsege(db, timesheet, orabere_gyorsito)

        honap_kulcs = (timesheet.start_date.year, timesheet.start_date.month)
        projekt_kulcs = project.id if project is not None else None
        if honap_kulcs not in honapok:
            honapok[honap_kulcs] = UtomunkaHonapIdo(
                ev=honap_kulcs[0],
                honap=honap_kulcs[1],
                honap_szoveg=ev_honap_szoveg(*honap_kulcs),
                total_minutes=0,
                total_cost=0 if lathat_koltseget else None,
            )
            projektek[honap_kulcs] = {}
        if projekt_kulcs not in projektek[honap_kulcs]:
            projektek[honap_kulcs][projekt_kulcs] = UtomunkaProjektIdo(
                project_id=projekt_kulcs,
                project_nev=project.nev if project is not None else None,
                projektkod=project.projektkod_szoveg if project is not None else None,
                anyagok_szama=0,
                total_minutes=0,
                total_cost=0 if lathat_koltseget else None,
            )
            anyagok[(*honap_kulcs, projekt_kulcs)] = set()

        honapok[honap_kulcs].total_minutes += percek
        projektek[honap_kulcs][projekt_kulcs].total_minutes += percek
        if lathat_koltseget and koltseg is not None:
            honapok[honap_kulcs].total_cost = (honapok[honap_kulcs].total_cost or 0) + koltseg
            sor = projektek[honap_kulcs][projekt_kulcs]
            sor.total_cost = (sor.total_cost or 0) + koltseg
        anyagok[(*honap_kulcs, projekt_kulcs)].add(deliverable.id)

    for honap_kulcs, honap in honapok.items():
        for projekt_kulcs, sor in projektek[honap_kulcs].items():
            sor.anyagok_szama = len(anyagok[(*honap_kulcs, projekt_kulcs)])
        honap.projektek = sorted(projektek[honap_kulcs].values(), key=lambda s: s.total_minutes, reverse=True)

    # Legfrissebb hónap elöl - azt nézi meg az ember legelőször.
    return sorted(honapok.values(), key=lambda h: (h.ev, h.honap), reverse=True)


@router.get("/{employee_id}/munkaszerzodesek", response_model=list[EmployeeDocumentRead])
def list_munkaszerzodesek(
    employee_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    return employee.documents


@router.post("/{employee_id}/munkaszerzodesek", response_model=EmployeeDocumentRead)
async def upload_munkaszerzodes(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    """Egy dokumentum (pl. munkaszerződés PDF/Word/kép) feltöltése egy
    munkatárshoz - egy munkatársnak tetszőleges számú fájlja lehet, mindegyik
    saját R2 kulcs alatt (a dokumentum id-ja alapján), egyenként törölhetők."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    filename = file.filename or "dokumentum"
    content_type = file.content_type or "application/octet-stream"
    doc = EmployeeDocument(employee_id=employee_id, filename=filename, content_type=content_type, storage_key="", url="")
    db.add(doc)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"munkaszerzodes/{employee_id}/{doc.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    doc.storage_key = key
    doc.url = url
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{employee_id}/munkaszerzodesek/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_munkaszerzodes(
    employee_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    doc = db.get(EmployeeDocument, document_id)
    if doc is None or doc.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="A dokumentum nem található")
    document_storage.delete_object(doc.storage_key)
    db.delete(doc)
    db.commit()


rates_router = build_crud_router(
    model=Rate,
    create_schema=RateCreate,
    update_schema=RateUpdate,
    read_schema=RateRead,
    prefix="/rates",
    tags=["crew"],
    page="/csapat",
)
