from datetime import date, timedelta

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import require_page_action
from app.models.contract import Contract, ContractPeriod, ContractType, megkotott_keretszerzodes
from app.models.employee import Employee
from app.services import keretszerzodes_kuldes
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


class KeretszerzodesKuldesIn(BaseModel):
    """Kiküldés paraméterei. A keltezés felülírható: egy ÚJ szerződés (pl. a
    régi lejárt) rendszerint mai keltezéssel megy ki."""

    keltezes: date | None = None
    #: Kiküldés után induljon-e új érvényességi időszak ezzel a keltezéssel.
    uj_idoszak: bool = False


class KeretszerzodesKuldesOut(BaseModel):
    contract_id: int
    szerzodes_allapota: str | None
    #: A KÉSZ PDF linkje (ez kerül a szerződés fájl-mezőjébe is).
    szerzodes_file_url: str | None
    #: A szerkeszthető Google Docs példány - ugyanabban a Drive mappában,
    #: mint a sablon és a PDF.
    doc_url: str | None = None
    cimzettek: list[str]


@router.post("/{contract_id}/kuldes", response_model=KeretszerzodesKuldesOut)
def send_keretszerzodes(
    contract_id: int,
    payload: KeretszerzodesKuldesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Keretszerződés generálása és kiküldése e-mailben.

    Akkor is használható, ha az embernek MÁR van keretszerződése: pont ez a
    dolga, hogy a régi (lejárt, felmondott) helyett újat lehessen küldeni.
    Ilyenkor nem nyitunk új sort - ugyanaz a bejegyzés kap friss papírt -, és
    kérésre indul hozzá egy új érvényességi időszak is (lásd
    models/contract.py ContractPeriod)."""
    szerzodes = _get_contract_or_404(db, contract_id)
    if not megkotott_keretszerzodes(szerzodes):
        raise HTTPException(
            status_code=400,
            detail="Ez a bejegyzés nem álló keretszerződés - eseti szerződést az Utókövetés oldalon lehet küldeni.",
        )
    employee = db.get(Employee, szerzodes.employee_id) if szerzodes.employee_id else None
    keltezes = payload.keltezes or date.today()

    try:
        doc_link, pdf_link, cim = keretszerzodes_kuldes.generalas_es_kuldes(
            szerzodes, employee, keltezes=keltezes
        )
    except keretszerzodes_kuldes.KeretszerzodesHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Hiányzó/lejárt Google hitelesítő adat - a felhasználó nem tud vele
        # mit kezdeni, de tudnia kell, hogy nem az ő adatával van baj.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    szerzodes.szerzodes_allapota = keretszerzodes_kuldes.KIKULDVE_ALLAPOT
    # A KÉSZ PDF-re hivatkozunk: ez az, amit a megbízott is megkapott. A
    # szerkeszthető Doc ott van mellette a sablon mappájában, és a válaszban
    # is visszaadjuk.
    szerzodes.szerzodes_file_url = pdf_link or doc_link
    szerzodes.keltezes = keltezes
    # Kiküldéskor a szerződés még nincs aláírva - a korábbi aláírt papír
    # jelölése nem vonatkozik az újra.
    szerzodes.alairva = False
    szerzodes.aktiv = True
    if payload.uj_idoszak:
        # Az előző, nyitott végű időszakot lezárjuk az új kezdete előtti napon:
        # két, egymást átfedő időszak félrevezető lenne.
        for idoszak in szerzodes.idoszakok:
            if idoszak.veg is None and (idoszak.kezdet is None or idoszak.kezdet < keltezes):
                idoszak.veg = keltezes - timedelta(days=1)
        db.add(ContractPeriod(contract_id=szerzodes.id, kezdet=keltezes, veg=None))
    db.commit()
    db.refresh(szerzodes)
    return KeretszerzodesKuldesOut(
        contract_id=szerzodes.id,
        szerzodes_allapota=szerzodes.szerzodes_allapota,
        szerzodes_file_url=szerzodes.szerzodes_file_url,
        doc_url=doc_link,
        cimzettek=cim,
    )
