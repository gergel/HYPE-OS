"""Alvállalkozók szerződése - projektenként összegyűjti, hogy a diszpó kiküldése
után kik vettek részt a projekten, akik SEM nem belsősök (Employee.tipus ==
"belsos"), SEM nincs már keretszerződésük (Contract, tipus="alvallalkozoi",
project_id=NULL, employee_id=ő) - nekik kell egyedi (eseti, projekthez kötött)
megbízási szerződést generálni és kiküldeni, vagy kihagyni (ha nem lesz
szerződés az adott projekttel).

A generálás+küldés a meglévő diszpó/szerződés-küldő motort (gdoc_template.py +
google_email.py) használja, a csatolt 'kulsos-eseti-szerzodes' Railway program
mezőkészletével (lásd hu_number_words.py a nettó összeg szöveges kiírásához)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import Contract, ContractType
from app.models.employee import Employee, EmployeeType
from app.models.project import Project
from app.schemas.contract import ContractRead
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message
from app.services.hu_number_words import szam_betukkel

router = APIRouter(prefix="/alvallalkozoi-szerzodesek", tags=["subcontractor-contracts"])

PAGE = "/alvallalkozoi-szerzodesek"

# A csatolt program email-sablonjának 1:1 portja (aláírás: "ADMINISZTRÁCIÓ",
# nem "GYÁRTÁS" - lásd services/dispo.py _SIGNATURE_HTML, ami a diszpóhoz
# tartozik, ide ezt a külön, adminisztrációs változatot használjuk).
_CONTRACT_EMAIL_HTML = """\
<p>Kedves Címzett,</p>
<p>
  Levelemhez csatoltan küldöm a tárgyban említett projektre vonatkozó szerződést.<br>
  Kérjük a projekt további dokumentációjához (teljesítés igazolása, számlázás és kifizetés)
  aláírva és/vagy pecsételve küldd vissza számunkra a csatolt dokumentumot, válasz e-mailben.
</p>
<p>Köszönettel,</p>
<br><br>
<table cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; font-size: 12px; color: #000;">
  <tr>
    <td style="vertical-align: middle; width: 150px;">
      <img src="https://raw.githubusercontent.com/gergel/ADMIN_projektkod/main/hype_logo_BG_03%20(2).png" alt="Hype logo" width="110">
    </td>
    <td style="padding-left: 20px; vertical-align: middle;">
      <p style="margin: 0; font-size: 12px; font-weight: bold;">HYPE PRODUCTIONS - ADMINISZTRÁCIÓ</p>
      <p style="margin: 0; color: #888; font-size: 12px;">Hype Productions Kft.</p>
    </td>
    <td style="padding-left: 40px; vertical-align: top; color: #888; font-size: 12px;">
      <p style="margin: 0;">Rahman Martin – cégvezető</p>
      <p style="margin: 0;">
        <a href="mailto:martin.rahman@hypestab.hu" style="color: #888; text-decoration: underline;">martin.rahman@hypestab.hu</a><br>
        +36 30 898 7600
      </p>
      <p style="margin: 0;">Barna Blanka – Back office manager</p>
      <p style="margin: 0;">
        <a href="mailto:blanka.barna@hypestab.hu" style="color: #888; text-decoration: underline;">blanka.barna@hypestab.hu</a><br>
        +36 30 758 8751
      </p>
    </td>
  </tr>
</table>
"""


def _pending_employees(project: Project, keretszerzodes_ids: set[int], handled_pairs: set[tuple[int, int]]) -> list[Employee]:
    return [
        e
        for e in project.crew
        if e.tipus != EmployeeType.BELSOS and e.id not in keretszerzodes_ids and (project.id, e.id) not in handled_pairs
    ]


def _load_contract_lookup(db: Session, employee_ids: set[int]) -> tuple[set[int], set[tuple[int, int]]]:
    if not employee_ids:
        return set(), set()
    contracts = (
        db.query(Contract)
        .filter(Contract.tipus == ContractType.ALVALLALKOZOI, Contract.employee_id.in_(employee_ids))
        .all()
    )
    keretszerzodes_ids = {c.employee_id for c in contracts if c.project_id is None}
    handled_pairs = {(c.project_id, c.employee_id) for c in contracts if c.project_id is not None}
    return keretszerzodes_ids, handled_pairs


class PendingProjectSummary(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    pending_count: int


@router.get("", response_model=list[PendingProjectSummary])
def list_pending_projects(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    projects = (
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
        .options(selectinload(Project.crew))
        .all()
    )
    all_employee_ids = {e.id for p in projects for e in p.crew if e.tipus != EmployeeType.BELSOS}
    keretszerzodes_ids, handled_pairs = _load_contract_lookup(db, all_employee_ids)

    result: list[PendingProjectSummary] = []
    for p in projects:
        pending = _pending_employees(p, keretszerzodes_ids, handled_pairs)
        if pending:
            result.append(
                PendingProjectSummary(
                    project_id=p.id, project_nev=p.nev, forgatas_datuma=p.forgatas_datuma, pending_count=len(pending)
                )
            )
    return result


class PendingEmployeeInfo(BaseModel):
    id: int
    full_name: str
    email: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    kepviselo: str | None
    nyilvantartasi_szam: str | None
    megbizas_targya: str | None
    plusz_afa: str | None


class PendingProjectDetail(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    pending: list[PendingEmployeeInfo]


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


@router.get("/{project_id}", response_model=PendingProjectDetail)
def get_pending_for_project(
    project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    project = _get_project_or_404(db, project_id)
    employee_ids = {e.id for e in project.crew if e.tipus != EmployeeType.BELSOS}
    keretszerzodes_ids, handled_pairs = _load_contract_lookup(db, employee_ids)
    pending = _pending_employees(project, keretszerzodes_ids, handled_pairs)
    return PendingProjectDetail(
        project_id=project.id,
        project_nev=project.nev,
        forgatas_datuma=project.forgatas_datuma,
        forgatas_datuma_vege=project.forgatas_datuma_vege,
        pending=[
            PendingEmployeeInfo(
                id=e.id,
                full_name=e.full_name,
                email=e.email,
                ceg_neve=e.vallakozas_neve,
                szekhely=e.vallakozas_szekhely,
                adoszam=e.vallalkozas_adoszama,
                kepviselo=e.vallalkozas_kepviselo,
                nyilvantartasi_szam=e.nyilvantartasi_szam,
                megbizas_targya=e.megbizas_targya,
                plusz_afa=e.plusz_afa,
            )
            for e in pending
        ],
    )


def _get_pending_employee_or_400(db: Session, project: Project, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található")
    if employee not in project.crew:
        raise HTTPException(status_code=400, detail="Ez a munkatárs nincs a projekt stábjában.")
    if employee.tipus == EmployeeType.BELSOS:
        raise HTTPException(status_code=400, detail="Belsős munkatársnak nem kell eseti szerződés.")
    existing = (
        db.query(Contract)
        .filter(Contract.project_id == project.id, Contract.employee_id == employee_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail="Ehhez a projekthez és emberhez már van szerződés-bejegyzés (kiküldve vagy kihagyva).",
        )
    keretszerzodes = (
        db.query(Contract)
        .filter(
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.employee_id == employee_id,
            Contract.project_id.is_(None),
        )
        .first()
    )
    if keretszerzodes is not None:
        raise HTTPException(
            status_code=400, detail="Ennek a munkatársnak már van keretszerződése, nincs szükség eseti szerződésre."
        )
    return employee


class GenerateContractIn(BaseModel):
    netto_osszeg: float
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    keltezes: date | None = None
    targy: str | None = None
    plusz_afa: str | None = None


@router.post("/{project_id}/{employee_id}/generate-and-send", response_model=ContractRead)
def generate_and_send(
    project_id: int,
    employee_id: int,
    payload: GenerateContractIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    project = _get_project_or_404(db, project_id)
    employee = _get_pending_employee_or_400(db, project, employee_id)
    if not employee.email:
        raise HTTPException(status_code=400, detail="A munkatársnak nincs email címe.")

    keltezes = payload.keltezes or date.today()
    targy = payload.targy or employee.megbizas_targya or ""
    afa = payload.plusz_afa or employee.plusz_afa or ""

    if payload.teljesites_vege and payload.teljesites_vege != payload.teljesites_kezdete:
        teljesites_str = (
            f"{payload.teljesites_kezdete.strftime('%Y.%m.%d.') if payload.teljesites_kezdete else ''} - "
            f"{payload.teljesites_vege.strftime('%Y.%m.%d.')}"
        )
    elif payload.teljesites_kezdete:
        teljesites_str = payload.teljesites_kezdete.strftime("%Y.%m.%d.")
    else:
        teljesites_str = ""

    doc_link = None
    pdf_bytes = None
    base_name = f"{project.forgatas_datuma or ''}_{project.nev or ''}_{employee.full_name}_szerződés"
    try:
        if settings.gdoc_alvallalkozoi_szerzodes_template_id:
            fields = {
                "nev": employee.vallakozas_neve or employee.full_name,
                "hely": employee.vallakozas_szekhely or "",
                "adoszam": employee.vallalkozas_adoszama or "",
                "targy": targy,
                "tido": teljesites_str,
                "netto": f"{payload.netto_osszeg:,.0f}".replace(",", " "),
                "kelt": keltezes.strftime("%Y.%m.%d."),
                "afa": afa,
                "nettoki": szam_betukkel(payload.netto_osszeg),
                "nyilvszam": employee.nyilvantartasi_szam or "",
                "kepvis": employee.vallalkozas_kepviselo or "",
                "projektnev": project.nev or "",
            }
            pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
                template_file_id=settings.gdoc_alvallalkozoi_szerzodes_template_id,
                base_name=base_name,
                fields=fields,
                output_folder_id=settings.gdoc_output_folder_id or settings.drive_folder_id or None,
            )
            doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

        send_message([employee.email], base_name, _CONTRACT_EMAIL_HTML, pdf_bytes=pdf_bytes, pdf_filename="szerzodes.pdf")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    contract = Contract(
        tipus=ContractType.ALVALLALKOZOI,
        employee_id=employee.id,
        project_id=project.id,
        ceg_neve=employee.vallakozas_neve or employee.full_name,
        szekhely=employee.vallakozas_szekhely,
        adoszam=employee.vallalkozas_adoszama,
        megbizas_targya=targy,
        vallalkozas_kepviseloje=employee.vallalkozas_kepviselo,
        vallalkozas_nyilvantartasi_szam=employee.nyilvantartasi_szam,
        keltezes=keltezes,
        email=employee.email,
        netto_osszeg=payload.netto_osszeg,
        teljesites_kezdete=payload.teljesites_kezdete,
        teljesites_vege=payload.teljesites_vege,
        plusz_afa=afa,
        szerzodes_allapota="Kiküldve",
        szerzodes_file_url=doc_link,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return ContractRead.model_validate(contract)


@router.post("/{project_id}/{employee_id}/skip", response_model=ContractRead)
def skip_contract(
    project_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A megbízott kihagyása - a projekt lezárható vele szerződés nélkül is,
    ő ezután nem jelenik meg többé a függő listán ennél a projektnél."""
    project = _get_project_or_404(db, project_id)
    employee = _get_pending_employee_or_400(db, project, employee_id)
    contract = Contract(
        tipus=ContractType.ALVALLALKOZOI,
        employee_id=employee.id,
        project_id=project.id,
        szerzodes_allapota="Kihagyva",
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return ContractRead.model_validate(contract)
