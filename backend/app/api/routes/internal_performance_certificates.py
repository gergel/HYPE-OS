"""Belsős TIG - havi, NEM projektenkénti teljesítésigazolás a belsős
(payroll-on lévő) munkatársakhoz: minden belsős embernek pontosan egy TIG-je
kell havonta, függetlenül attól, hány projekten dolgozott azon a hónapon -
ez a végpont-csoport ezért nem projektre, hanem (employee_id, ev, honap)
hármasra épül. Az admin oldal (lásd frontend app/(app)/belsos-tig/page.tsx)
alapértelmezetten a folyó hónapot mutatja, és felsorolja AZ ÖSSZES belsős
munkatársat - akinek még nincs TIG-je erre a hónapra, annak létre kell hozni
vagy kihagyni (ha épp nem dolgozott)."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee, EmployeeType
from app.models.finance import Expense
from app.models.internal_performance_certificate import (
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.schemas.internal_performance_certificate import InternalPerformanceCertificateRead
from app.services import document_storage

router = APIRouter(prefix="/belsos-tig", tags=["internal-performance-certificates"])

PAGE = "/belsos-tig"

TERMINAL_STATUSES = {"Kész", "Kihagyva"}


def _belsos_employees(db: Session) -> list[Employee]:
    return db.query(Employee).filter(Employee.tipus == EmployeeType.BELSOS).order_by(Employee.full_name).all()


def _get_or_create(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate:
    existing = (
        db.query(InternalPerformanceCertificate)
        .filter(
            InternalPerformanceCertificate.employee_id == employee_id,
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
        )
        .first()
    )
    if existing is not None:
        return existing
    record = InternalPerformanceCertificate(employee_id=employee_id, ev=ev, honap=honap, allapot="Készítés alatt")
    db.add(record)
    db.flush()
    return record


def _validate_belsos_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.tipus != EmployeeType.BELSOS:
        raise HTTPException(status_code=400, detail="Ez a végpont csak belsős munkatársakhoz használható.")
    return employee


class MonthEmployeeInfo(BaseModel):
    id: int
    full_name: str
    email: str | None
    record: InternalPerformanceCertificateRead | None


@router.get("", response_model=list[MonthEmployeeInfo])
def list_month(
    ev: int | None = None,
    honap: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Az adott hónap (alapértelmezetten a folyó hónap) összes belsős
    munkatársa + a hozzájuk tartozó TIG-bejegyzés (ha van) - a frontend ebből
    dönti el, kinél van még teendő (nincs bejegyzés / Készítés alatt), és
    kinél van már lezárva (Kész / Kihagyva)."""
    today = date.today()
    ev = ev or today.year
    honap = honap or today.month
    employees = _belsos_employees(db)
    if not employees:
        return []
    records = (
        db.query(InternalPerformanceCertificate)
        .filter(
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
            InternalPerformanceCertificate.employee_id.in_([e.id for e in employees]),
        )
        .all()
    )
    lookup = {r.employee_id: r for r in records}
    return [
        MonthEmployeeInfo(
            id=e.id,
            full_name=e.full_name,
            email=e.email,
            record=InternalPerformanceCertificateRead.model_validate(lookup[e.id]) if e.id in lookup else None,
        )
        for e in employees
    ]


class TigDraftIn(BaseModel):
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    megjegyzes: str | None = None


_DRAFT_FIELDS = ("netto_osszeg", "plusz_afa", "megjegyzes")


def _apply_draft_fields(record: InternalPerformanceCertificate, payload: TigDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(record, field, value)


@router.post("/{employee_id}/{ev}/{honap}/save", response_model=InternalPerformanceCertificateRead)
def save_draft(
    employee_id: int,
    ev: int,
    honap: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee_id, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    _apply_draft_fields(record, payload)
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/kesz", response_model=InternalPerformanceCertificateRead)
def finalize(
    employee_id: int,
    ev: int,
    honap: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Nincs sablon-generálás/email-küldés belsősöknél (lásd fájl-fejléc) - a
    'kész' állapot csak azt jelzi, hogy az összeg rögzítve van, és jöhet a
    számla feltöltése."""
    _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee_id, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    _apply_draft_fields(record, payload)
    if not record.netto_osszeg or record.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    record.allapot = "Kész"
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/skip", response_model=InternalPerformanceCertificateRead)
def skip(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee_id, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    record.allapot = "Kihagyva"
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


def _get_finalized_or_404(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate:
    record = (
        db.query(InternalPerformanceCertificate)
        .filter(
            InternalPerformanceCertificate.employee_id == employee_id,
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nem tartozik Belsős TIG bejegyzés.")
    if record.allapot != "Kész":
        raise HTTPException(status_code=400, detail="Számla csak lezárt (Kész) Belsős TIG-hez tölthető fel.")
    return record


@router.post("/{employee_id}/{ev}/{honap}/szamla", response_model=InternalPerformanceCertificateRead)
async def upload_szamla(
    employee_id: int,
    ev: int,
    honap: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy Belsős TIG-hez tetszőleges számú számla tölthető fel - minden
    hívás egy ÚJ számla-sort hoz létre (nem írja felül az előzőt), lásd
    InternalPerformanceCertificateInvoice modell-kommentje."""
    record = _get_finalized_or_404(db, employee_id, ev, honap)
    filename = file.filename or "szamla"
    content_type = file.content_type or "application/octet-stream"
    invoice = InternalPerformanceCertificateInvoice(
        certificate_id=record.id, filename=filename, content_type=content_type, storage_key="", url=""
    )
    db.add(invoice)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"belsos-tig-szamla/{employee_id}/{ev}-{honap:02d}-{invoice.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    invoice.storage_key = key
    invoice.url = url
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.delete("/{employee_id}/{ev}/{honap}/szamla/{invoice_id}", response_model=InternalPerformanceCertificateRead)
def delete_szamla(
    employee_id: int,
    ev: int,
    honap: int,
    invoice_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    record = _get_finalized_or_404(db, employee_id, ev, honap)
    invoice = db.get(InternalPerformanceCertificateInvoice, invoice_id)
    if invoice is None or invoice.certificate_id != record.id:
        raise HTTPException(status_code=404, detail="A számla nem található.")
    document_storage.delete_object(invoice.storage_key)
    db.delete(invoice)
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/szamla-kifizetve", response_model=InternalPerformanceCertificateRead)
def mark_szamla_kifizetve(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    record = _get_finalized_or_404(db, employee_id, ev, honap)
    if not record.invoices:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")

    # float(): a Numeric oszlop az adatbázisból Decimal-ként jön vissza, és a
    # Decimal * float TypeError-t dob (lásd performance_certificates.py).
    brutto = (
        round(float(record.netto_osszeg) * 1.27, 2)
        if (record.plusz_afa and record.netto_osszeg)
        else record.netto_osszeg
    )

    expense = db.get(Expense, record.expense_id) if record.expense_id is not None else None
    if expense is None:
        expense = Expense(
            megnevezes=f"Belsős TIG - {record.employee.full_name} - {ev}.{honap:02d}",
            employee_id=record.employee_id,
            tipus="belsos",
            netto=record.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        record.expense_id = expense.id
    else:
        expense.netto = record.netto_osszeg
        expense.brutto = brutto

    expense.kesz = True
    expense.fizetes_datuma = date.today()
    record.szamla_kifizetve = True
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)
