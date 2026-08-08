"""Mettől meddig volt valaki belsős - a havi TIG-teendők időbeli határa.

Ha egy belsős munkatárs csak márciusban lépett be, januárra és februárra nincs
mit kérni tőle; ha augusztusban kilépett, szeptemberre sincs. E nélkül az ilyen
hónapok örökre "hiányzó TIG"-ként állnának a Belsős TIG oldalon.

Egy embernél TÖBB időszak is felvehető (kilép, majd visszajön) - ugyanaz a
szerkezet, mint a keretszerződés érvényességénél (lásd
routes/contracts.py idoszakok végpontjai).

Ha valakinél egyetlen időszak sincs, a rendszer a munkatárs első/utolsó
munkanapjára esik vissza, annak híján pedig minden hónapra vár TIG-et - lásd
services/belsos_idoszak.py."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import Employee, EmployeeType
from app.services import belsos_idoszak as szolgaltatas

router = APIRouter(prefix="/belsos-idoszakok", tags=["belsos-idoszakok"])

# A belsős TIG oldal jogosultságához kötjük: aki a havi TIG-eket kezeli, az
# tudja azt is, ki mikor volt itt.
PAGE = "/belsos-tig"


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


class EmployeeIdoszakok(BaseModel):
    employee_id: int
    full_name: str
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


class BelsosAttekintes(BaseModel):
    """Egy sor a Belsős TIG oldal "ki mettől meddig" áttekintésén."""

    employee_id: int
    full_name: str
    idoszakok: list[IdoszakRead] = []
    elso_munkanap: date | None = None
    utolso_munkanap: date | None = None
    #: Emberi összefoglaló ("2024.03.01. – 2025.08.31., 2026.02.01. –").
    osszefoglalo: str
    #: Vár-e tőle a rendszer TIG-et a MOSTANI hónapban.
    most_belsos: bool


@router.get("", response_model=list[BelsosAttekintes])
def list_belsosok(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    """Minden belsős, a felvitt időszakaival - a Belsős TIG oldal
    beállító-szekciója ezt listázza."""
    ma = date.today()
    eredmeny: list[BelsosAttekintes] = []
    for e in szolgaltatas.belsosok(db):
        idoszakok = list(e.belsos_idoszakok)
        osszefoglalo = szolgaltatas.idoszak_szoveg(idoszakok)
        if not osszefoglalo and (e.elso_munkanap or e.utolso_munkanap):
            kezdet = e.elso_munkanap.strftime("%Y.%m.%d.") if e.elso_munkanap else ""
            veg = e.utolso_munkanap.strftime("%Y.%m.%d.") if e.utolso_munkanap else ""
            osszefoglalo = f"{kezdet} – {veg}".strip()
        eredmeny.append(
            BelsosAttekintes(
                employee_id=e.id,
                full_name=e.full_name,
                idoszakok=[IdoszakRead.model_validate(i) for i in idoszakok],
                elso_munkanap=e.elso_munkanap,
                utolso_munkanap=e.utolso_munkanap,
                osszefoglalo=osszefoglalo,
                most_belsos=szolgaltatas.belsos_volt(e, ma.year, ma.month),
            )
        )
    return eredmeny
