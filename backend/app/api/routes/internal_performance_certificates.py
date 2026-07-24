"""Belsős TIG - a Külsős TIG (performance_certificates.py) párja belsős
munkatársakhoz. Egyszerűbb, mert belsősöknek nincs eseti/keretszerződés-
előfeltétele és nem kap Google Docs sablon-generálást/emailt - csak egy
összeg rögzítése, majd (a Külsős TIG-hez hasonlóan) számla feltöltése és
kifizetettként jelölése, ami Expense sort hoz létre a Pénzügy -> Kiadások
összesítőhöz (lásd spec 2.2)."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee, EmployeeType
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.project import Project
from app.schemas.internal_performance_certificate import InternalPerformanceCertificateRead
from app.services import document_storage

router = APIRouter(prefix="/belsos-tig", tags=["internal-performance-certificates"])

PAGE = "/teljesitesi-igazolasok"

TERMINAL_STATUSES = {"Kész", "Kihagyva"}


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


def _belsos_candidates(project: Project) -> list[Employee]:
    return [e for e in project.crew if e.tipus == EmployeeType.BELSOS]


def _load_tig_lookup(db: Session, employee_ids: set[int]) -> dict[tuple[int, int], InternalPerformanceCertificate]:
    if not employee_ids:
        return {}
    rows = (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.employee_id.in_(employee_ids))
        .all()
    )
    return {(r.project_id, r.employee_id): r for r in rows}


def _pending(
    project: Project, lookup: dict[tuple[int, int], InternalPerformanceCertificate]
) -> list[tuple[Employee, InternalPerformanceCertificate | None]]:
    result: list[tuple[Employee, InternalPerformanceCertificate | None]] = []
    for e in _belsos_candidates(project):
        existing = lookup.get((project.id, e.id))
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
def list_belsos_tig_ready_projects(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    projects = db.query(Project).options(selectinload(Project.crew)).all()
    eligible = [p for p in projects if _belsos_candidates(p)]
    all_employee_ids = {e.id for p in eligible for e in _belsos_candidates(p)}
    lookup = _load_tig_lookup(db, all_employee_ids)

    result: list[PendingProjectSummary] = []
    for p in eligible:
        pending = _pending(p, lookup)
        if pending:
            result.append(
                PendingProjectSummary(
                    project_id=p.id, project_nev=p.nev, forgatas_datuma=p.forgatas_datuma, pending_count=len(pending)
                )
            )
    return result


class DraftInfo(BaseModel):
    allapot: str | None
    netto_osszeg: float | None
    plusz_afa: bool | None
    teljesites_kezdete: date | None
    teljesites_vege: date | None
    megjegyzes: str | None


class PendingEmployeeInfo(BaseModel):
    id: int
    full_name: str
    draft: DraftInfo | None


class PendingProjectDetail(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    pending: list[PendingEmployeeInfo]


def _draft_info(c: InternalPerformanceCertificate | None) -> DraftInfo | None:
    if c is None:
        return None
    return DraftInfo(
        allapot=c.allapot,
        netto_osszeg=c.netto_osszeg,
        plusz_afa=c.plusz_afa,
        teljesites_kezdete=c.teljesites_kezdete,
        teljesites_vege=c.teljesites_vege,
        megjegyzes=c.megjegyzes,
    )


@router.get("/{project_id}", response_model=PendingProjectDetail)
def get_pending_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    project = _get_project_or_404(db, project_id)
    employee_ids = {e.id for e in _belsos_candidates(project)}
    lookup = _load_tig_lookup(db, employee_ids)
    pending = _pending(project, lookup)
    return PendingProjectDetail(
        project_id=project.id,
        project_nev=project.nev,
        forgatas_datuma=project.forgatas_datuma,
        pending=[PendingEmployeeInfo(id=e.id, full_name=e.full_name, draft=_draft_info(existing)) for e, existing in pending],
    )


@router.get("/{project_id}/all", response_model=list[InternalPerformanceCertificateRead])
def list_all_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    rows = (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.project_id == project_id)
        .all()
    )
    return [InternalPerformanceCertificateRead.model_validate(r) for r in rows]


def _validate_belsos_employee(db: Session, project: Project, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található")
    if employee not in project.crew:
        raise HTTPException(status_code=400, detail="Ez a munkatárs nincs a projekt stábjában.")
    if employee.tipus != EmployeeType.BELSOS:
        raise HTTPException(status_code=400, detail="Ez a végpont csak belsős munkatársakhoz használható.")
    return employee


def _get_or_create_draft(db: Session, project: Project, employee: Employee) -> InternalPerformanceCertificate:
    existing = (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.project_id == project.id, InternalPerformanceCertificate.employee_id == employee.id)
        .first()
    )
    if existing is not None:
        if existing.allapot in TERMINAL_STATUSES:
            raise HTTPException(status_code=400, detail="Ehhez a projekthez és emberhez már véglegesített Belsős TIG tartozik.")
        return existing
    draft = InternalPerformanceCertificate(project_id=project.id, employee_id=employee.id, allapot="Készítés alatt")
    db.add(draft)
    db.flush()
    return draft


class TigDraftIn(BaseModel):
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    megjegyzes: str | None = None


_DRAFT_FIELDS = ("netto_osszeg", "plusz_afa", "teljesites_kezdete", "teljesites_vege", "megjegyzes")


def _apply_draft_fields(draft: InternalPerformanceCertificate, payload: TigDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(draft, field, value)


@router.post("/{project_id}/{employee_id}/save", response_model=InternalPerformanceCertificateRead)
def save_draft(
    project_id: int,
    employee_id: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    project = _get_project_or_404(db, project_id)
    employee = _validate_belsos_employee(db, project, employee_id)
    draft = _get_or_create_draft(db, project, employee)
    _apply_draft_fields(draft, payload)
    db.commit()
    db.refresh(draft)
    return InternalPerformanceCertificateRead.model_validate(draft)


@router.post("/{project_id}/{employee_id}/kesz", response_model=InternalPerformanceCertificateRead)
def finalize_draft(
    project_id: int,
    employee_id: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Nincs sablon-generálás/email-küldés belsősöknél (lásd fájl-fejléc) - a
    'kész' állapot csak azt jelzi, hogy az összeg rögzítve van, és jöhet a
    számla feltöltése."""
    project = _get_project_or_404(db, project_id)
    employee = _validate_belsos_employee(db, project, employee_id)
    draft = _get_or_create_draft(db, project, employee)
    _apply_draft_fields(draft, payload)
    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    draft.allapot = "Kész"
    db.commit()
    db.refresh(draft)
    return InternalPerformanceCertificateRead.model_validate(draft)


@router.post("/{project_id}/{employee_id}/skip", response_model=InternalPerformanceCertificateRead)
def skip_tig(
    project_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    project = _get_project_or_404(db, project_id)
    employee = _validate_belsos_employee(db, project, employee_id)
    draft = _get_or_create_draft(db, project, employee)
    draft.allapot = "Kihagyva"
    db.commit()
    db.refresh(draft)
    return InternalPerformanceCertificateRead.model_validate(draft)


def _get_finalized_or_404(db: Session, project_id: int, employee_id: int) -> InternalPerformanceCertificate:
    cert = (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.project_id == project_id, InternalPerformanceCertificate.employee_id == employee_id)
        .first()
    )
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projekthez és emberhez nem tartozik Belsős TIG bejegyzés.")
    if cert.allapot != "Kész":
        raise HTTPException(status_code=400, detail="Számla csak lezárt (Kész) Belsős TIG-hez tölthető fel.")
    return cert


@router.post("/{project_id}/{employee_id}/szamla", response_model=InternalPerformanceCertificateRead)
async def upload_szamla(
    project_id: int,
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    cert = _get_finalized_or_404(db, project_id, employee_id)
    filename = file.filename or "szamla"
    content_type = file.content_type or "application/octet-stream"
    ext = os.path.splitext(filename)[1]
    key = f"belsos-tig-szamla/{project_id}/{employee_id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    cert.szamla_url = url
    cert.szamla_storage_key = key
    db.commit()
    db.refresh(cert)
    return InternalPerformanceCertificateRead.model_validate(cert)


@router.post("/{project_id}/{employee_id}/szamla-kifizetve", response_model=InternalPerformanceCertificateRead)
def mark_szamla_kifizetve(
    project_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    cert = _get_finalized_or_404(db, project_id, employee_id)
    if not cert.szamla_url:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")
    project = _get_project_or_404(db, project_id)

    brutto = round(cert.netto_osszeg * 1.27, 2) if (cert.plusz_afa and cert.netto_osszeg) else cert.netto_osszeg

    expense = db.get(Expense, cert.expense_id) if cert.expense_id is not None else None
    if expense is None:
        expense = Expense(
            megnevezes=f"Belsős TIG - {cert.employee.full_name} - {project.projektkod_szoveg or project.nev or ''}".strip(" -"),
            project_code_id=project.project_code_id,
            employee_id=cert.employee_id,
            tipus="belsos",
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
    return InternalPerformanceCertificateRead.model_validate(cert)
