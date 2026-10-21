"""Adminisztráció ellenőrzése - a tulajdonos ellenőrző oldala (lásd
services/admin_ellenorzes.py és services/lara_figyeles.py).

HOZZÁFÉRÉS: csak a tulajdonos (a védett rendszergazda), és akinek ezt az
oldalt KIFEJEZETTEN megadták a Beállításokban - a figyelt kolléga SOHA, akkor
sem, ha valaki megadná neki (a felhasználó kérése: "csak nekem jelezzen")."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, van_kifejezett_oldal_joga, vedett_rendszergazda
from app.models.admin_ellenorzes import ALAP_HATARIDOK, LaraFigyelesJelzes
from app.models.employee import Employee
from app.models.user_access import PageAccessConfig
from app.services import admin_ellenorzes, lara_figyeles

router = APIRouter(prefix="/admin-ellenorzes", tags=["admin-ellenorzes"])

PAGE = admin_ellenorzes.PAGE


def lathatja(db: Session, user: Employee) -> bool:
    b = admin_ellenorzes.beallitas(db)
    if b.figyelt_employee_id is not None and b.figyelt_employee_id == user.id:
        return False
    if vedett_rendszergazda(user):
        return True
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == user.id))
    return van_kifejezett_oldal_joga(config.page_permissions if config else None, PAGE)


def csak_tulajdonos(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)) -> Employee:
    if not lathatja(db, user):
        raise HTTPException(status_code=403, detail="Ezt az oldalt csak a tulajdonos láthatja.")
    return user


@router.get("/hozzaferes")
def hozzaferes(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)) -> dict:
    """A menü ebből tudja, mutassa-e az oldalt (bárki kérdezheti, csak igen/nem)."""
    return {"lathatja": lathatja(db, user)}


class BeallitasOut(BaseModel):
    figyelt_employee_id: int | None
    figyelt_nev: str | None
    lara_figyeles: bool
    hataridok: dict[str, int]
    utolso_futas_at: datetime | None
    #: Ettől a naptól nézi az ellenőrzés a dolgokat (a kolléga kezdete).
    figyeles_kezdete: date
    #: Lara heti áttekintése: mikor volt utoljára, és mikor lesz a következő.
    heti_attekintes_at: datetime | None
    kovetkezo_heti_at: datetime
    #: Be van kapcsolva, és a mostani heti áttekintés még nem futott le (a
    #: következő órás körben jön).
    heti_esedekes: bool


class BeallitasIn(BaseModel):
    figyelt_employee_id: int | None = None
    lara_figyeles: bool | None = None
    hataridok: dict[str, int] | None = None
    figyeles_kezdete: date | None = None
    #: A figyelt kolléga TÖRLÉSE (None nem jelenti azt, hogy "ne változzon").
    figyelt_torles: bool = False


def _beallitas_out(db: Session) -> BeallitasOut:
    b = admin_ellenorzes.beallitas(db)
    figyelt = db.get(Employee, b.figyelt_employee_id) if b.figyelt_employee_id else None
    return BeallitasOut(
        figyelt_employee_id=b.figyelt_employee_id,
        figyelt_nev=figyelt.full_name if figyelt else None,
        lara_figyeles=bool(b.lara_figyeles),
        hataridok=admin_ellenorzes.hataridok(b),
        utolso_futas_at=b.utolso_futas_at,
        figyeles_kezdete=admin_ellenorzes.kezdet(b),
        heti_attekintes_at=b.heti_attekintes_at,
        kovetkezo_heti_at=lara_figyeles.kovetkezo_heti(lara_figyeles._most()),
        heti_esedekes=bool(b.lara_figyeles) and lara_figyeles.heti_esedekes(b, lara_figyeles._most()),
    )


@router.get("/beallitasok", response_model=BeallitasOut)
def beallitasok(db: Session = Depends(get_db), _user: Employee = Depends(csak_tulajdonos)):
    out = _beallitas_out(db)
    db.commit()
    return out


@router.put("/beallitasok", response_model=BeallitasOut)
def beallitasok_mentese(payload: BeallitasIn, db: Session = Depends(get_db), user: Employee = Depends(csak_tulajdonos)):
    b = admin_ellenorzes.beallitas(db)
    if payload.figyelt_torles:
        b.figyelt_employee_id = None
    elif payload.figyelt_employee_id is not None:
        if payload.figyelt_employee_id == user.id:
            raise HTTPException(status_code=400, detail="Saját magadat nem figyeltetheted.")
        if db.get(Employee, payload.figyelt_employee_id) is None:
            raise HTTPException(status_code=404, detail="A munkatárs nem található.")
        b.figyelt_employee_id = payload.figyelt_employee_id
    if payload.lara_figyeles is not None:
        b.lara_figyeles = payload.lara_figyeles
    if payload.hataridok is not None:
        uj = admin_ellenorzes.hataridok(b)
        for k, v in payload.hataridok.items():
            if k not in ALAP_HATARIDOK:
                raise HTTPException(status_code=400, detail=f"Ismeretlen határidő: {k}")
            if not 0 <= int(v) <= 365:
                raise HTTPException(status_code=400, detail="A határidő 0 és 365 nap között lehet.")
            uj[k] = int(v)
        b.hataridok = uj
    if payload.figyeles_kezdete is not None:
        b.figyeles_kezdete = payload.figyeles_kezdete
    db.commit()
    return _beallitas_out(db)


@router.get("/naplo")
def naplo(
    napok: int = Query(14, ge=1, le=365),
    employee_id: int | None = None,
    csak_kivetel: bool = False,
    db: Session = Depends(get_db),
    _user: Employee = Depends(csak_tulajdonos),
) -> list[dict]:
    b = admin_ellenorzes.beallitas(db)
    return admin_ellenorzes.naplo(
        db, napok=napok, employee_id=employee_id, csak_kivetel=csak_kivetel, tol=admin_ellenorzes.kezdet(b))


@router.get("/kivetelek")
def kivetelek(
    napok: int | None = Query(None, ge=1, le=3650),
    csak_nyitott: bool = False,
    db: Session = Depends(get_db),
    _user: Employee = Depends(csak_tulajdonos),
) -> list[dict]:
    """`napok` nélkül: minden a kezdőnap óta."""
    b = admin_ellenorzes.beallitas(db)
    return admin_ellenorzes.kivetelek(db, napok=napok, csak_nyitott=csak_nyitott, tol=admin_ellenorzes.kezdet(b))


class JelolesIn(BaseModel):
    kulcs: str
    dontes: str
    megjegyzes: str | None = None
    #: Visszadobásnál feladat menjen-e a figyelt kollégának.
    feladat: bool = False
    cim: str | None = None
    link: str | None = None


@router.post("/kivetelek/jeloles")
def kivetel_jelolese(payload: JelolesIn, db: Session = Depends(get_db), user: Employee = Depends(csak_tulajdonos)) -> dict:
    try:
        j = admin_ellenorzes.jeloles(
            db, kulcs=payload.kulcs, dontes=payload.dontes, megjegyzes=payload.megjegyzes, felhasznalo=user,
            feladat=payload.feladat, cim=payload.cim, link=payload.link,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": j.id, "dontes": j.dontes, "task_id": j.task_id}


@router.get("/lejart")
def lejart(db: Session = Depends(get_db), _user: Employee = Depends(csak_tulajdonos)) -> list[dict]:
    b = admin_ellenorzes.beallitas(db)
    return admin_ellenorzes.lejart_hianyok(db, hatarido=admin_ellenorzes.hataridok(b), tol=admin_ellenorzes.kezdet(b))


@router.get("/osszesito")
def osszesito(db: Session = Depends(get_db), _user: Employee = Depends(csak_tulajdonos)) -> dict:
    b = admin_ellenorzes.beallitas(db)
    return {
        **admin_ellenorzes.heti_osszesito(db, figyelt_id=b.figyelt_employee_id, kezdonap=admin_ellenorzes.kezdet(b)),
        "szamok": admin_ellenorzes.allapot_szamok(db),
    }


@router.get("/lara/jelzesek")
def lara_jelzesek(
    nyitott: bool = True, db: Session = Depends(get_db), _user: Employee = Depends(csak_tulajdonos)
) -> list[dict]:
    q = select(LaraFigyelesJelzes)
    if nyitott:
        q = q.where(LaraFigyelesJelzes.lezarva_at.is_(None))
    sorok = db.scalars(q.order_by(LaraFigyelesJelzes.letrejott_at.desc()).limit(300)).all()
    return [
        {
            "id": j.id, "szabaly": j.szabaly, "szint": j.szint, "cim": j.cim, "leiras": j.leiras, "link": j.link,
            "letrejott_at": j.letrejott_at, "lezarva_at": j.lezarva_at,
        }
        for j in sorok
    ]


@router.post("/lara/jelzesek/{jelzes_id}/lezaras")
def lara_jelzes_lezarasa(jelzes_id: int, db: Session = Depends(get_db), user: Employee = Depends(csak_tulajdonos)) -> dict:
    j = db.get(LaraFigyelesJelzes, jelzes_id)
    if j is None:
        raise HTTPException(status_code=404, detail="A jelzés nem található.")
    j.lezarva_at = j.lezarva_at or lara_figyeles._most()
    j.lezarta_id = user.id
    db.commit()
    return {"id": j.id, "lezarva_at": j.lezarva_at}


@router.post("/lara/futtatas")
def lara_futtatas(db: Session = Depends(get_db), _user: Employee = Depends(csak_tulajdonos)) -> dict:
    """Kézi átnézés - ugyanaz, mint a heti (szabályok + összefoglaló az előző
    hétről); csak olvas és jelez."""
    return lara_figyeles.heti_attekintes(db, kenyszer=True)
