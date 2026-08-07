from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import require_page_action
from app.models.contract import Contract, ContractPeriod, ContractType, megkotott_keretszerzodes
from app.models.employee import Employee
from app.schemas.contract import (
    ContractCreate,
    ContractPeriodCreate,
    ContractPeriodRead,
    ContractRead,
    ContractUpdate,
)

PAGE = "/penzugyek"

router = build_crud_router(
    model=Contract,
    create_schema=ContractCreate,
    update_schema=ContractUpdate,
    read_schema=ContractRead,
    prefix="/contracts",
    tags=["contracts"],
    page=PAGE,
)


class KeretszerzodesCreate(BaseModel):
    employee_id: int


def _get_contract_or_404(db: Session, contract_id: int) -> Contract:
    szerzodes = db.get(Contract, contract_id)
    if szerzodes is None:
        raise HTTPException(status_code=404, detail="A szerződés nem található.")
    return szerzodes


def _cegadat(employee: Employee) -> dict:
    """A munkatárs saját cégadatai a szerződés mezőire képezve."""
    return {
        "ceg_neve": employee.vallakozas_neve or employee.full_name,
        "szekhely": employee.vallakozas_szekhely,
        "adoszam": employee.vallalkozas_adoszama,
        "megbizas_targya": employee.megbizas_targya,
        "vallalkozas_kepviseloje": employee.vallalkozas_kepviselo,
        "vallalkozas_nyilvantartasi_szam": employee.nyilvantartasi_szam,
        "keltezes": employee.keltezes_datuma,
        "email": employee.email,
    }


@router.post("/keretszerzodes", response_model=ContractRead, status_code=201)
def create_keretszerzodes(
    payload: KeretszerzodesCreate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Egy meglévő crew tag (bármelyik tipus, akár belsős is) felvétele a
    'Keretszerződések' nézetbe - a cégadatokat az Employee saját, már meglévő
    (vállalkozás neve/székhely/adószám/képviselő/nyilvántartási szám) mezőiből
    másoljuk át, ugyanúgy ahogy a projekt-szintű 'Szerződés készítés' teszi
    (lásd services/contract_actions.py apply_szerzodes_keszites)."""
    employee = db.get(Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A kiválasztott munkatárs nem található.")
    existing = (
        db.query(Contract)
        .filter(
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.employee_id == employee.id,
            Contract.project_id.is_(None),
            Contract.keretszerzodes.is_(True),
        )
        .first()
    )
    if existing is not None and megkotott_keretszerzodes(existing):
        raise HTTPException(status_code=400, detail="Ennek a munkatársnak már van keretszerződése.")

    # A munkatársnak lehet ESETI megbízási szerződése is (a Notion-lapjáról, a
    # cégadataiból) - azt nem léptetjük elő és nem írjuk felül: a keretszerződés
    # külön sor, külön szekció (lásd models/contract.py Contract.keretszerzodes).
    contract = Contract(
        tipus=ContractType.ALVALLALKOZOI,
        employee_id=employee.id,
        project_id=None,
        keretszerzodes=True,
        szerzodes_allapota="Aktív",
        **_cegadat(employee),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return ContractRead.model_validate(contract)


@router.get("/{contract_id}/idoszakok", response_model=list[ContractPeriodRead])
def list_idoszakok(
    contract_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    """Egy keretszerződés érvényességi időszakai, időrendben."""
    _get_contract_or_404(db, contract_id)
    return [
        ContractPeriodRead.model_validate(i)
        for i in db.query(ContractPeriod).filter(ContractPeriod.contract_id == contract_id).all()
    ]


@router.post("/{contract_id}/idoszakok", response_model=ContractPeriodRead, status_code=201)
def create_idoszak(
    contract_id: int,
    payload: ContractPeriodCreate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Új érvényességi időszak felvétele.

    Egy emberrel nem feltétlenül folyamatos a keretszerződéses viszony: van
    egy időszakra, aztán fél évig nincs, majd újra - ezért vehető fel több is
    egymás után (lásd models/contract.py ContractPeriod)."""
    _get_contract_or_404(db, contract_id)
    if payload.kezdet is not None and payload.veg is not None and payload.veg < payload.kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet korábban, mint a kezdete.")
    idoszak = ContractPeriod(contract_id=contract_id, **payload.model_dump())
    db.add(idoszak)
    db.commit()
    db.refresh(idoszak)
    return ContractPeriodRead.model_validate(idoszak)


@router.patch("/idoszakok/{idoszak_id}", response_model=ContractPeriodRead)
def update_idoszak(
    idoszak_id: int,
    payload: ContractPeriodCreate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    idoszak = db.get(ContractPeriod, idoszak_id)
    if idoszak is None:
        raise HTTPException(status_code=404, detail="Az időszak nem található.")
    if payload.kezdet is not None and payload.veg is not None and payload.veg < payload.kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet korábban, mint a kezdete.")
    for mezo, ertek in payload.model_dump().items():
        setattr(idoszak, mezo, ertek)
    db.commit()
    db.refresh(idoszak)
    return ContractPeriodRead.model_validate(idoszak)


@router.delete("/idoszakok/{idoszak_id}", status_code=204)
def delete_idoszak(
    idoszak_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Időszak törlése. Ha az utolsó is elfogy, a keretszerződés újra időbeli
    korlát nélkül érvényes lesz (lásd keretszerzodes_ervenyes)."""
    idoszak = db.get(ContractPeriod, idoszak_id)
    if idoszak is None:
        raise HTTPException(status_code=404, detail="Az időszak nem található.")
    db.delete(idoszak)
    db.commit()
