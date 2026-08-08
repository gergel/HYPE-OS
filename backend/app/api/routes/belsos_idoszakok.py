"""Belsős beállítások: JOGVISZONY és IDŐSZAKOK - a havi TIG-teendők határai.

Két, egymást kiegészítő beállítás:

- a JOGVISZONY azt mondja meg, KELL-E egyáltalán havi TIG. A bejelentett
  alkalmazott bérét bérszámfejtés fizeti: nála nincs TIG, nincs számla és nincs
  kifizetés-lépés, a havi teendő pusztán annyi, hogy a fizetése be legyen írva
  (lásd models/employee.py BelsosJogviszony);
- az IDŐSZAKOK azt, hogy MELY HÓNAPOKRA várjuk el.

Mettől meddig volt valaki belsős - a havi TIG-teendők időbeli határa.

Ha egy belsős munkatárs csak márciusban lépett be, januárra és februárra nincs
mit kérni tőle; ha augusztusban kilépett, szeptemberre sincs. E nélkül az ilyen
hónapok örökre "hiányzó TIG"-ként állnának a Belsős TIG oldalon.

Egy embernél TÖBB időszak is felvehető (kilép, majd visszajön) - ugyanaz a
szerkezet, mint a keretszerződés érvényességénél (lásd
routes/contracts.py idoszakok végpontjai).

Ha valakinél egyetlen időszak sincs, a rendszer a munkatárs első/utolsó
munkanapjára esik vissza, annak híján pedig minden hónapra vár TIG-et - lásd
services/belsos_idoszak.py.

A felület a MUNKATÁRS SAJÁT ADATLAPJÁN van (Csapat > az illető lapja), az
első/utolsó munkanap mellett - oda tartozik, hiszen a munkatárs törzsadata.
Ezért a jogosultsága is a Csapat oldalé."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import BelsosJogviszony, Employee, EmployeeType

router = APIRouter(prefix="/belsos-idoszakok", tags=["belsos-idoszakok"])

# A munkatárs adatlapján szerkesztik (az első/utolsó munkanap mellett), ezért
# a Csapat oldal jogosultsága vonatkozik rá.
PAGE = "/csapat"


class IdoszakRead(BaseModel):
    id: int
    employee_id: int
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None

    model_config = {"from_attributes": True}


class IdoszakIn(BaseModel):
    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


class JogviszonyIn(BaseModel):
    #: "megbizas" | "alkalmazott"
    jogviszony: BelsosJogviszony


class EmployeeIdoszakok(BaseModel):
    employee_id: int
    full_name: str
    #: "megbizas" (havonta számláz, kell TIG) | "alkalmazott" (bejelentett,
    #: nem kell TIG - csak a fizetését kell beírni).
    jogviszony: str = BelsosJogviszony.MEGBIZAS.value
    idoszakok: list[IdoszakRead] = []
    #: A visszaesési adat, ha nincs egyetlen időszak sem - a felület ezt írja
    #: ki magyarázatként.
    elso_munkanap: date | None = None
    utolso_munkanap: date | None = None


def _get_employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található.")
    return employee


def _nezet(employee: Employee) -> EmployeeIdoszakok:
    return EmployeeIdoszakok(
        employee_id=employee.id,
        full_name=employee.full_name,
        jogviszony=employee.belsos_jogviszony.value,
        idoszakok=[IdoszakRead.model_validate(i) for i in employee.belsos_idoszakok],
        elso_munkanap=employee.elso_munkanap,
        utolso_munkanap=employee.utolso_munkanap,
    )


@router.get("/{employee_id}", response_model=EmployeeIdoszakok)
def get_idoszakok(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    return _nezet(_get_employee_or_404(db, employee_id))


@router.post("/{employee_id}", response_model=EmployeeIdoszakok, status_code=201)
def create_idoszak(
    employee_id: int,
    payload: IdoszakIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Új belsős időszak felvétele.

    Nyitott vég = "azóta is itt van", nyitott kezdet = "a kezdetektől"."""
    employee = _get_employee_or_404(db, employee_id)
    if employee.tipus != EmployeeType.BELSOS:
        raise HTTPException(
            status_code=400,
            detail="Belsős időszakot csak belsős munkatársnál lehet megadni.",
        )
    if payload.kezdet is not None and payload.veg is not None and payload.veg < payload.kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet korábban, mint a kezdete.")
    employee.belsos_idoszakok.append(BelsosIdoszak(**payload.model_dump()))
    db.commit()
    db.refresh(employee)
    return _nezet(employee)


@router.patch("/idoszak/{idoszak_id}", response_model=EmployeeIdoszakok)
def update_idoszak(
    idoszak_id: int,
    payload: IdoszakIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    idoszak = db.get(BelsosIdoszak, idoszak_id)
    if idoszak is None:
        raise HTTPException(status_code=404, detail="Az időszak nem található.")
    if payload.kezdet is not None and payload.veg is not None and payload.veg < payload.kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet korábban, mint a kezdete.")
    for mezo, ertek in payload.model_dump().items():
        setattr(idoszak, mezo, ertek)
    db.commit()
    return _nezet(_get_employee_or_404(db, idoszak.employee_id))


@router.delete("/idoszak/{idoszak_id}", response_model=EmployeeIdoszakok)
def delete_idoszak(
    idoszak_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Időszak törlése. Ha ezzel elfogy az összes, a rendszer visszaesik a
    munkatárs első/utolsó munkanapjára."""
    idoszak = db.get(BelsosIdoszak, idoszak_id)
    if idoszak is None:
        raise HTTPException(status_code=404, detail="Az időszak nem található.")
    employee_id = idoszak.employee_id
    db.delete(idoszak)
    db.commit()
    return _nezet(_get_employee_or_404(db, employee_id))


@router.put("/{employee_id}/jogviszony", response_model=EmployeeIdoszakok)
def set_jogviszony(
    employee_id: int,
    payload: JogviszonyIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Bejelentett alkalmazott vagy folyamatos megbízási szerződéses?

    Alkalmazottra állítva a rendszer nem vár tőle havi TIG-et, számlát és
    kifizetés-jelölést - a havi teendő csak a fizetés beírása lesz. A MÁR
    elkészült TIG-eket ez nem törli: azok megmaradnak, csak új hónapokra nem
    kérünk többet."""
    employee = _get_employee_or_404(db, employee_id)
    if employee.tipus != EmployeeType.BELSOS:
        raise HTTPException(
            status_code=400,
            detail="A jogviszony csak belsős munkatársnál értelmezhető.",
        )
    employee.belsos_jogviszony = payload.jogviszony
    db.commit()
    db.refresh(employee)
    return _nezet(employee)
