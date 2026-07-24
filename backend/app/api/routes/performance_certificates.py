"""Teljesítési igazolás (TIG) - miután egy projekten mindenkinek megvan az
eseti szerződése (lásd subcontractor_contracts.py - "Kiküldve" vagy
"Kihagyva" mindenkinél, akinek egyáltalán kellett), a projekt "TIG-re kész"
állapotba kerül: ekkor minden nem belsős stábtagnak (a keretszerződéseseknek
IS - a TIG a konkrét munka elvégzését igazolja, nem azt, hogy van-e álló
keretszerződése) teljesítési igazolást kell generálni és kiküldeni, vagy
kihagyni.

Ugyanaz a kétlépéses (mentés majd generálás-és-küldés, vagy kihagyás)
életciklus, mint az eseti szerződéseknél, csak külön táblában
(PerformanceCertificate) és a csatolt 'TIG-alvalalkozo' program
mezőkészletével/sablon-placeholdereivel."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.routes.subcontractor_contracts import _load_contract_lookup, _pending_employees
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee, EmployeeType
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.schemas.performance_certificate import PerformanceCertificateRead
from app.services import document_storage
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message
from app.services.hu_number_words import szam_betukkel

router = APIRouter(prefix="/teljesitesi-igazolasok", tags=["performance-certificates"])

PAGE = "/teljesitesi-igazolasok"

TERMINAL_STATUSES = {"Kiküldve", "Kihagyva"}

_TIG_EMAIL_HTML = """\
<p>Kedves Címzett,</p>
<p>
  Alább a <b>{projektdatum}</b> dátumú, tárgyban említett projekt kódú esemény teljesítési igazolása.<br>
  Kérjük figyelj rá, hogy a számla teljesítési dátuma egyezzen a teljesítési igazolás teljesítési dátumával.
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


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


def _load_tig_lookup(db: Session, employee_ids: set[int]) -> dict[tuple[int, int], PerformanceCertificate]:
    if not employee_ids:
        return {}
    rows = db.query(PerformanceCertificate).filter(PerformanceCertificate.employee_id.in_(employee_ids)).all()
    return {(r.project_id, r.employee_id): r for r in rows}


def _tig_candidates(project: Project) -> list[Employee]:
    """A TIG-et igénylő emberek egy projekten: minden nem belsős stábtag,
    FÜGGETLENÜL attól, hogy van-e keretszerződése (szemben az eseti
    szerződés-populációval, ahol a keretszerződésesek ki vannak zárva)."""
    return [e for e in project.crew if e.tipus != EmployeeType.BELSOS]


def _is_szerzodes_phase_done(db: Session, project: Project) -> bool:
    """Igaz, ha a projekten mindenkinek (aki egyáltalán eseti szerződést
    igényelt: nem belsős és nincs keretszerződése) megvan a szerződés
    státusza (kiküldve vagy kihagyva) - lásd subcontractor_contracts.py."""
    employee_ids = {e.id for e in project.crew if e.tipus != EmployeeType.BELSOS}
    keretszerzodes_ids, project_contracts = _load_contract_lookup(db, employee_ids)
    pending = _pending_employees(project, keretszerzodes_ids, project_contracts)
    return len(pending) == 0


def _tig_pending_employees(
    project: Project, tig_lookup: dict[tuple[int, int], PerformanceCertificate]
) -> list[tuple[Employee, PerformanceCertificate | None]]:
    result: list[tuple[Employee, PerformanceCertificate | None]] = []
    for e in _tig_candidates(project):
        existing = tig_lookup.get((project.id, e.id))
        if existing is not None and existing.allapot in TERMINAL_STATUSES:
            continue
        result.append((e, existing))
    return result


class PendingProjectSummary(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    pending_count: int


@router.get("", response_model=list[PendingProjectSummary])
def list_tig_ready_projects(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    projects = (
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
        .options(selectinload(Project.crew))
        .all()
    )
    eligible = [p for p in projects if _tig_candidates(p) and _is_szerzodes_phase_done(db, p)]
    all_employee_ids = {e.id for p in eligible for e in _tig_candidates(p)}
    tig_lookup = _load_tig_lookup(db, all_employee_ids)

    result: list[PendingProjectSummary] = []
    for p in eligible:
        pending = _tig_pending_employees(p, tig_lookup)
        if pending:
            result.append(
                PendingProjectSummary(
                    project_id=p.id, project_nev=p.nev, forgatas_datuma=p.forgatas_datuma, pending_count=len(pending)
                )
            )
    return result


class DraftInfo(BaseModel):
    allapot: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    megbizas_targya: str | None
    netto_osszeg: float | None
    teljesites_kezdete: date | None
    teljesites_vege: date | None
    keltezes: date | None
    plusz_afa: bool | None


class PendingEmployeeInfo(BaseModel):
    id: int
    full_name: str
    email: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    megbizas_targya: str | None
    plusz_afa: bool | None
    draft: DraftInfo | None


class PendingProjectDetail(BaseModel):
    project_id: int
    project_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    pending: list[PendingEmployeeInfo]
    tig_ready: bool


def _draft_info(c: PerformanceCertificate | None) -> DraftInfo | None:
    if c is None:
        return None
    return DraftInfo(
        allapot=c.allapot,
        ceg_neve=c.ceg_neve,
        szekhely=c.szekhely,
        adoszam=c.adoszam,
        megbizas_targya=c.megbizas_targya,
        netto_osszeg=c.netto_osszeg,
        teljesites_kezdete=c.teljesites_kezdete,
        teljesites_vege=c.teljesites_vege,
        keltezes=c.keltezes,
        plusz_afa=c.plusz_afa,
    )


@router.get("/{project_id}", response_model=PendingProjectDetail)
def get_pending_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    project = _get_project_or_404(db, project_id)
    tig_ready = bool(_tig_candidates(project)) and _is_szerzodes_phase_done(db, project)
    pending: list[tuple[Employee, PerformanceCertificate | None]] = []
    if tig_ready:
        employee_ids = {e.id for e in _tig_candidates(project)}
        tig_lookup = _load_tig_lookup(db, employee_ids)
        pending = _tig_pending_employees(project, tig_lookup)
    return PendingProjectDetail(
        project_id=project.id,
        project_nev=project.nev,
        projektkod=project.projektkod_szoveg,
        forgatas_datuma=project.forgatas_datuma,
        forgatas_datuma_vege=project.forgatas_datuma_vege,
        tig_ready=tig_ready,
        pending=[
            PendingEmployeeInfo(
                id=e.id,
                full_name=e.full_name,
                email=e.email,
                ceg_neve=e.vallakozas_neve,
                szekhely=e.vallakozas_szekhely,
                adoszam=e.vallalkozas_adoszama,
                megbizas_targya=e.megbizas_targya,
                plusz_afa=e.plusz_afa,
                draft=_draft_info(existing),
            )
            for e, existing in pending
        ],
    )


@router.get("/{project_id}/all", response_model=list[PerformanceCertificateRead])
def list_all_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az adott projekt ÖSSZES TIG-bejegyzése (bármilyen állapotban) - a
    kiküldött (Kiküldve) tételekhez itt jelenik meg a számla-feltöltés és
    kifizetettként jelölés vezérlő a frontenden (lásd
    PerformanceCertificateManager), a still-pending (Készítés alatt) tételek
    a get_pending_for_project végpontból jönnek."""
    rows = db.query(PerformanceCertificate).filter(PerformanceCertificate.project_id == project_id).all()
    return [PerformanceCertificateRead.model_validate(r) for r in rows]


def _validate_pending_employee(db: Session, project: Project, employee_id: int) -> Employee:
    if not _is_szerzodes_phase_done(db, project):
        raise HTTPException(
            status_code=400, detail="Ezen a projekten még nem mindenkinek van meg a szerződése - TIG csak azután készíthető."
        )
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található")
    if employee not in project.crew:
        raise HTTPException(status_code=400, detail="Ez a munkatárs nincs a projekt stábjában.")
    if employee.tipus == EmployeeType.BELSOS:
        raise HTTPException(status_code=400, detail="Belsős munkatársnak nem kell teljesítési igazolás.")
    return employee


def _get_or_create_draft(db: Session, project: Project, employee: Employee) -> PerformanceCertificate:
    existing = (
        db.query(PerformanceCertificate)
        .filter(PerformanceCertificate.project_id == project.id, PerformanceCertificate.employee_id == employee.id)
        .first()
    )
    if existing is not None:
        if existing.allapot in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Ehhez a projekthez és emberhez már véglegesített TIG-bejegyzés tartozik (kiküldve vagy kihagyva).",
            )
        return existing
    draft = PerformanceCertificate(
        project_id=project.id,
        employee_id=employee.id,
        allapot="Készítés alatt",
        ceg_neve=employee.vallakozas_neve or employee.full_name,
        szekhely=employee.vallakozas_szekhely,
        adoszam=employee.vallalkozas_adoszama,
        megbizas_targya=employee.megbizas_targya,
        plusz_afa=employee.plusz_afa,
        email=employee.email,
    )
    db.add(draft)
    db.flush()
    return draft


class TigDraftIn(BaseModel):
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    keltezes: date | None = None
    plusz_afa: bool | None = None


_DRAFT_FIELDS = (
    "ceg_neve",
    "szekhely",
    "adoszam",
    "megbizas_targya",
    "netto_osszeg",
    "teljesites_kezdete",
    "teljesites_vege",
    "keltezes",
    "plusz_afa",
)


def _apply_draft_fields(draft: PerformanceCertificate, payload: TigDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(draft, field, value)


@router.post("/{project_id}/{employee_id}/save", response_model=PerformanceCertificateRead)
def save_draft(
    project_id: int,
    employee_id: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    project = _get_project_or_404(db, project_id)
    employee = _validate_pending_employee(db, project, employee_id)
    draft = _get_or_create_draft(db, project, employee)
    _apply_draft_fields(draft, payload)
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


@router.post("/{project_id}/{employee_id}/generate-and-send", response_model=PerformanceCertificateRead)
def generate_and_send(
    project_id: int,
    employee_id: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    project = _get_project_or_404(db, project_id)
    employee = _validate_pending_employee(db, project, employee_id)
    draft = _get_or_create_draft(db, project, employee)
    _apply_draft_fields(draft, payload)

    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    if not employee.email:
        raise HTTPException(status_code=400, detail="A munkatársnak nincs email címe.")

    keltezes = draft.keltezes or date.today()
    draft.keltezes = keltezes

    if draft.teljesites_vege and draft.teljesites_vege != draft.teljesites_kezdete:
        teljesites_str = (
            f"{draft.teljesites_kezdete.strftime('%Y.%m.%d.') if draft.teljesites_kezdete else ''} - "
            f"{draft.teljesites_vege.strftime('%Y.%m.%d.')}"
        )
    elif draft.teljesites_kezdete:
        teljesites_str = draft.teljesites_kezdete.strftime("%Y.%m.%d.")
    else:
        teljesites_str = ""

    projektdatum = project.forgatas_datuma.strftime("%Y.%m.%d.") if project.forgatas_datuma else ""

    doc_link = None
    pdf_bytes = None
    base_name = f"{projektdatum}_{draft.ceg_neve or employee.full_name}_{project.projektkod_szoveg or ''}_TIG"
    try:
        if settings.gdoc_tig_template_id:
            fields = {
                "nev": draft.ceg_neve or employee.full_name,
                "hely": draft.szekhely or "",
                "adoszam": draft.adoszam or "",
                "targy": draft.megbizas_targya or "",
                "tido": teljesites_str,
                "projkod": project.projektkod_szoveg or "",
                "netto": f"{draft.netto_osszeg:,.0f}".replace(",", " "),
                "kelt": keltezes.strftime("%Y.%m.%d."),
                "afa": "+ ÁFA" if draft.plusz_afa else "",
                "nettoki": szam_betukkel(draft.netto_osszeg),
            }
            pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
                template_file_id=settings.gdoc_tig_template_id,
                base_name=base_name,
                fields=fields,
                output_folder_id=settings.gdoc_output_folder_id or settings.drive_folder_id or None,
            )
            doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

        subject = f"{draft.ceg_neve or employee.full_name}_{project.projektkod_szoveg or ''} - Projekt_TIG"
        html = _TIG_EMAIL_HTML.format(projektdatum=projektdatum or "–")
        send_message([employee.email], subject, html, pdf_bytes=pdf_bytes, pdf_filename="teljesitesi_igazolas.pdf")
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük el, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    draft.allapot = "Kiküldve"
    draft.file_url = doc_link
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


@router.post("/{project_id}/{employee_id}/skip", response_model=PerformanceCertificateRead)
def skip_tig(
    project_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    project = _get_project_or_404(db, project_id)
    employee = _validate_pending_employee(db, project, employee_id)
    draft = _get_or_create_draft(db, project, employee)
    draft.allapot = "Kihagyva"
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


def _get_sent_certificate_or_404(db: Session, project_id: int, employee_id: int) -> PerformanceCertificate:
    """A TIG-hez tartozó számla feltöltése/kifizetése csak azután lehetséges,
    hogy magát a TIG-et már kiküldtük (lásd generate_and_send) - eddig a
    pontig nincs mihez számlát kötni."""
    cert = (
        db.query(PerformanceCertificate)
        .filter(PerformanceCertificate.project_id == project_id, PerformanceCertificate.employee_id == employee_id)
        .first()
    )
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projekthez és emberhez nem tartozik TIG-bejegyzés.")
    if cert.allapot != "Kiküldve":
        raise HTTPException(status_code=400, detail="Számla csak kiküldött TIG-hez tölthető fel.")
    return cert


@router.post("/{project_id}/{employee_id}/szamla", response_model=PerformanceCertificateRead)
async def upload_szamla(
    project_id: int,
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A kiküldött TIG-hez tartozó (külső számlázási rendszerben kiállított)
    számla feltöltése - ez még nem jelenti a kifizetést, csak a dokumentum
    rögzítését (lásd /szamla-kifizetve a tényleges Pénzügy-be kerüléshez)."""
    cert = _get_sent_certificate_or_404(db, project_id, employee_id)
    filename = file.filename or "szamla"
    content_type = file.content_type or "application/octet-stream"
    ext = os.path.splitext(filename)[1]
    key = f"tig-szamla/{project_id}/{employee_id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    cert.szamla_url = url
    cert.szamla_storage_key = key
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post("/{project_id}/{employee_id}/szamla-kifizetve", response_model=PerformanceCertificateRead)
def mark_szamla_kifizetve(
    project_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A feltöltött számla kifizetettként jelölése - ez hozza létre (vagy
    frissíti, ha már létezik) a Pénzügy -> Kiadások-ban megjelenő Expense
    sort, a projekt project_code_id-jához és az alvállalkozóhoz kötve, hogy a
    költség a helyes projekthez kapcsolódjon (lásd spec 2.1)."""
    cert = _get_sent_certificate_or_404(db, project_id, employee_id)
    if not cert.szamla_url:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")
    project = _get_project_or_404(db, project_id)

    brutto = round(cert.netto_osszeg * 1.27, 2) if (cert.plusz_afa and cert.netto_osszeg) else cert.netto_osszeg

    if cert.expense_id is not None:
        expense = db.get(Expense, cert.expense_id)
    else:
        expense = None

    if expense is None:
        expense = Expense(
            megnevezes=f"TIG - {cert.ceg_neve or ''} - {project.projektkod_szoveg or project.nev or ''}".strip(" -"),
            project_code_id=project.project_code_id,
            employee_id=cert.employee_id,
            tipus="kulsos",
            netto=cert.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        cert.expense_id = expense.id
    else:
        expense.netto = cert.netto_osszeg
        expense.brutto = brutto

    expense.kesz = True
    expense.fizetes_datuma = date.today()
    cert.szamla_kifizetve = True
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)
