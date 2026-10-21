from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import FOGLALAS_OLDAL, get_current_user, require_page_action
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project
from app.services import eszkoz_statisztika
from app.services.hu_datum import BUDAPEST_IDOZONA
from app.schemas.equipment import (
    AssignmentCreate,
    AssignmentRead,
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
)

def _rendszerbe_kerules(data: dict, db: Session) -> dict:
    """Új eszköznél a RENDSZERBE KERÜLÉS időpontja magától kitöltődik (a
    felhasználó kérése) - ha kézzel megadták, az marad."""
    if not data.get("rendszerbe_kerules_idopontja"):
        data["rendszerbe_kerules_idopontja"] = datetime.now(BUDAPEST_IDOZONA).replace(tzinfo=None, microsecond=0)
    return data


def _statisztika_kimenet(sorok: list[dict], db: Session, _user: Employee) -> list[dict]:
    """A kimenő eszköz-sorokba a SZÁMOLT munka-statisztika kerül (hány napot
    dolgozott, hány forgatáson vett részt, hol volt utoljára) - lásd
    services/eszkoz_statisztika.py. Egy forgatás nélküli eszköznél a régi
    (Notionból jött / kézzel írt) „ahol utoljára volt” szöveg megmarad."""
    idk = [s["id"] for s in sorok if isinstance(s.get("id"), int)]
    stat = eszkoz_statisztika.statisztikak(db, idk)
    for sor in sorok:
        s = stat.get(sor.get("id"))
        if s is None:
            continue
        sor["hany_napot_dolgozott"] = float(s.napok_szama)
        sor["hany_forgatason_vett_reszt"] = str(len(s.forgatasok))
        if s.ahol_utoljara_volt:
            sor["ahol_utoljara_volt"] = s.ahol_utoljara_volt
    return sorok


router = build_crud_router(
    model=Equipment,
    create_schema=EquipmentCreate,
    update_schema=EquipmentUpdate,
    read_schema=EquipmentRead,
    prefix="/equipment",
    tags=["equipment"],
    page="/felszereles",
    entity_type="equipment",
    before_create=_rendszerbe_kerules,
    kimenet_szuro=_statisztika_kimenet,
)


class ArchivalasIn(BaseModel):
    ok: str | None = None


class JovobeliFoglalas(BaseModel):
    project_id: int
    nev: str
    datum: date | None


class ArchivalasValasz(BaseModel):
    id: int
    archivalva_at: datetime | None
    archivalas_oka: str | None
    #: Az eszköz még előttünk álló forgatásai - ezekről le kell venni (az
    #: archiválás nem törli a foglalást; a „Technika ready” is jelzi).
    jovobeli_foglalasok: list[JovobeliFoglalas] = []


def _jovobeli_foglalasok(db: Session, equipment_id: int) -> list[JovobeliFoglalas]:
    ma = datetime.now(BUDAPEST_IDOZONA).date()
    sorok = db.execute(
        select(Project.id, Project.nev, Project.forgatas_datuma, Project.forgatas_datuma_vege)
        .join(Assignment, Assignment.project_id == Project.id)
        .where(Assignment.equipment_id == equipment_id)
        .distinct()
    ).all()
    ki = [
        JovobeliFoglalas(project_id=pid, nev=nev, datum=kezd)
        for pid, nev, kezd, vege in sorok
        if (vege or kezd) is not None and (vege or kezd) >= ma
    ]
    return sorted(ki, key=lambda f: f.datum or date.max)


@router.post("/{equipment_id}/archivalas", response_model=ArchivalasValasz)
def eszkoz_archivalas(
    equipment_id: int,
    payload: ArchivalasIn | None = None,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action("/felszereles", "edit")),
):
    """ARCHIVÁLÁS (a felhasználó kérése, 2026-10): az eszköz eltűnik a
    Felszerelés listáról, nem foglalható forgatásra és nem írható ki az
    eszközkivitelben - a múltbeli forgatásainál (foglalás, kivitel) viszont
    megmarad. Semmit nem töröl; visszaállítható. A válasz felsorolja, melyik
    még előttünk álló forgatásra van foglalva - azokról le kell venni."""
    e = db.get(Equipment, equipment_id)
    if e is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Az eszköz nem található.")
    if e.archivalva_at is None:
        e.archivalva_at = datetime.now(BUDAPEST_IDOZONA)
        e.archivalta_id = user.id
    e.archivalas_oka = ((payload.ok if payload else None) or "").strip() or e.archivalas_oka
    db.commit()
    return ArchivalasValasz(id=e.id, archivalva_at=e.archivalva_at, archivalas_oka=e.archivalas_oka,
                            jovobeli_foglalasok=_jovobeli_foglalasok(db, e.id))


@router.post("/{equipment_id}/visszaallitas", response_model=ArchivalasValasz)
def eszkoz_visszaallitas(
    equipment_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/felszereles", "edit")),
):
    """Az archivált eszköz visszaállítása: újra látszik a listán, foglalható
    és kiírható."""
    e = db.get(Equipment, equipment_id)
    if e is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Az eszköz nem található.")
    e.archivalva_at = None
    e.archivalta_id = None
    e.archivalas_oka = None
    db.commit()
    return ArchivalasValasz(id=e.id, archivalva_at=None, archivalas_oka=None)


class EszkozForgatas(BaseModel):
    project_id: int
    nev: str
    helyszin: str | None = None
    kezdet: date
    vege: date
    napok: int
    #: "kivitel" (az eszközkivitel szerint kint volt) vagy "foglalas" (a
    #: projektre volt foglalva - ahol még nincs kivitel).
    forras: str


@router.get("/{equipment_id}/forgatasok", response_model=list[EszkozForgatas])
def eszkoz_forgatasai(
    equipment_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Mely forgatásokon dolgozott az eszköz, forgatásonként hány napot -
    ugyanaz a számítás, ami a „hány napot dolgozott” mezőt adja."""
    if db.get(Equipment, equipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment nem található")
    stat = eszkoz_statisztika.statisztikak(db, [equipment_id])[equipment_id]
    return [
        EszkozForgatas(
            project_id=f.project_id,
            nev=f.nev,
            helyszin=f.helyszin,
            kezdet=f.kezdet,
            vege=f.vege,
            napok=len(f.napok),
            forras=f.forras,
        )
        for f in stat.forgatasok
    ]

assignments_router = APIRouter(prefix="/assignments", tags=["equipment"])


def _project_range(project: Project) -> tuple | None:
    if not project.forgatas_datuma:
        return None
    return project.forgatas_datuma, (project.forgatas_datuma_vege or project.forgatas_datuma)


def _ranges_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start <= b_end and b_start <= a_end


@assignments_router.get("", response_model=list[AssignmentRead])
def list_assignments(
    skip: int = 0,
    limit: int = 100,
    equipment_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    stmt = select(Assignment)
    if equipment_id is not None:
        stmt = stmt.where(Assignment.equipment_id == equipment_id)
    if project_id is not None:
        stmt = stmt.where(Assignment.project_id == project_id)
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@assignments_router.post(
    "",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    # NEM a /felszereles oldal joga kell hozzá, hanem a FOGLALÁSÉ: a technikát a
    # PROJEKTEN vezetik fel, tehát akinek a projektre (vagy a diszpón át a
    # projektre) szerkesztési joga van, az tud eszközt kérni - magát a leltárat
    # viszont ettől még nem bővítheti. Lásd core/security.OLDAL_ALIASZOK.
    dependencies=[Depends(require_page_action(FOGLALAS_OLDAL, "create"))],
)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db)):
    """Eszköz (Leltár, egyedi vagy darabszámos) hozzárendelése egy projekthez -
    ez a Leltár + Stock igények egységes hozzáadási mechanizmusa: 'asset' eszköznél
    qty=1, 'stock' eszköznél a kért darabszám. Az esetleges ütközést (más projekt
    ugyanarra az eszközre, átfedő napon, vagy a stock keret túllépése) NEM itt
    blokkoljuk - a projekten a 'Technika ready' ellenőrzés (POST
    /projects/{id}/technika-check) adja a hivatalos, nap-szintű riportot, ahogy az
    eredeti Notion workflow-ban is: szabadon fel lehet venni mindent, a checkbox
    futtatja le a validációt.

    Ha nincs megadva kivitel_datuma/visszahozatal_datuma, a projekt forgatási
    dátumaiból (forgatas_datuma / forgatas_datuma_vege) töltjük ki."""
    equipment = db.get(Equipment, payload.equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment nem található")
    project = db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")

    # UGYANAZ az eszköz, UGYANARRA a projektre és időszakra: nem nyitunk új
    # sort (készletesnél +db, egyedinél a meglévő sor) - a közös szabály a
    # services/eszkoz_foglalas.py-ban él, Lara technikai listája is azt hívja.
    from app.services.eszkoz_foglalas import ArchivaltEszkoz, hozzarendel

    data = payload.model_dump(exclude={"equipment_id", "project_id"})
    try:
        obj, _ = hozzarendel(db, project, equipment, **data)
    except ArchivaltEszkoz as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(obj)
    return obj


class AssignmentQtyIn(BaseModel):
    qty: int


@assignments_router.patch(
    "/{assignment_id}",
    response_model=AssignmentRead,
    dependencies=[Depends(require_page_action(FOGLALAS_OLDAL, "edit"))],
)
def update_assignment_qty(assignment_id: int, payload: AssignmentQtyIn, db: Session = Depends(get_db)):
    """Egy MÁR HOZZÁADOTT eszköz darabszámának átírása (a felhasználó kérése)
    - készletes (stock) eszköznél van értelme, a felület csak ott kínálja.
    Az ütközés-ellenőrzés itt sem fut (lásd create_assignment): a hivatalos
    riport a "Technika ready" gomb."""
    obj = db.get(Assignment, assignment_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment nem található")
    if payload.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A darabszám legalább 1.")
    obj.qty = payload.qty
    db.commit()
    db.refresh(obj)
    return obj


@assignments_router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_page_action(FOGLALAS_OLDAL, "delete"))],
)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):
    obj = db.get(Assignment, assignment_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment nem található")
    db.delete(obj)
    db.commit()


@router.get("/{equipment_id}/availability")
def equipment_availability(
    equipment_id: int,
    project_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy eszköz elérhetősége egy adott projekt forgatási napjaira - asset eszköznél
    foglalt-e már (más projekthez), stock eszköznél hány db szabad a teljes
    mennyiségből. A hozzáadás UI-ban ez mutatja élőben, mennyi elérhető, mielőtt
    a felhasználó ténylegesen hozzáadná. Ha a felhasználó a hozzáadáskor a projekt
    teljes forgatási időszakától eltérő (szűkebb) kiviteli/visszahozatali dátumot
    ad meg, azt start_date/end_date-ként átadva ARRA az időszakra kérdezhető le az
    elérhetőség (nem a teljes projekt-időszakra)."""
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment nem található")
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nem található")

    if start_date is not None:
        project_range = (start_date, end_date or start_date)
    else:
        project_range = _project_range(project)
    if project_range is None:
        return {"track_mode": equipment.track_mode.value, "available": None, "detail": "Nincs forgatási dátum a projekten."}
    start, end = project_range

    other_assignments = db.scalars(
        select(Assignment).where(Assignment.equipment_id == equipment_id, Assignment.project_id != project_id)
    ).all()

    if equipment.track_mode == TrackMode.ASSET:
        for a in other_assignments:
            other = db.get(Project, a.project_id)
            other_range = _project_range(other) if other else None
            if other_range and _ranges_overlap(start, end, *other_range):
                return {"track_mode": "asset", "available": False, "detail": f"Foglalt: {other.nev}"}
        return {"track_mode": "asset", "available": True, "detail": None}

    foglalt = 0
    for a in other_assignments:
        other = db.get(Project, a.project_id)
        other_range = _project_range(other) if other else None
        if other_range and _ranges_overlap(start, end, *other_range):
            foglalt += a.qty

    if equipment.osszes_mennyiseg is None:
        # Nincs megadva "Összes mennyiség" (gyakori a Notion-importált
        # tételeknél) - ez NEM azt jelenti, hogy 0 db van belőle, csak azt,
        # hogy nem ismert a keret. Ilyenkor nem korlátozzuk a hozzáadást.
        return {
            "track_mode": "stock",
            "available": None,
            "keret": None,
            "foglalt": foglalt,
            "detail": "Nincs megadva összes mennyiség ennél az eszköznél - a hozzáadás nem korlátozott.",
        }

    keret = equipment.osszes_mennyiseg
    return {"track_mode": "stock", "available": max(keret - foglalt, 0), "keret": keret, "foglalt": foglalt}
