from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import require_page_action
from app.models.contract import Contract, ContractType, megkotott_keretszerzodes
from app.models.employee import Employee
from app.schemas.contract import ContractCreate, ContractRead, ContractUpdate

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
