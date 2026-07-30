"""Belsős TIG - havi, NEM projektenkénti teljesítésigazolás a belsős
(payroll-on lévő) munkatársakhoz: minden belsős embernek pontosan egy TIG-je
kell havonta, függetlenül attól, hány projekten dolgozott azon a hónapon -
ez a végpont-csoport ezért nem projektre, hanem (employee_id, ev, honap)
hármasra épül. Az admin oldal (lásd frontend app/(app)/belsos-tig/page.tsx)
alapértelmezetten a folyó hónapot mutatja, és felsorolja AZ ÖSSZES belsős
munkatársat - akinek még nincs TIG-je erre a hónapra, annak létre kell hozni
vagy kihagyni (ha épp nem dolgozott).

A hónapot MINDIG a teljesítés dátuma határozza meg, és mindig az azt megelőző
hónapot jelenti (2026.06.20-i teljesítés = a 2026. MÁJUSI TIG) - ha az admin
átírja a teljesítési dátumot úgy, hogy másik hónapot jelöl, a bejegyzés
átkerül abba a hónapba (lásd _apply_teljesites_honap)."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
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
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message
from app.services.hu_datum import elozo_honap, ev_honap_szoveg, kovetkezo_honap_elseje
from app.services.hu_number_words import szam_betukkel

router = APIRouter(prefix="/belsos-tig", tags=["internal-performance-certificates"])

PAGE = "/belsos-tig"

# A "Kész" a korábbi, küldés nélküli életciklusból maradt itt: a régi
# bejegyzések ebben az állapotban vannak, és ugyanúgy lezártnak számítanak,
# mint az azóta bevezetett "Kiküldve".
TERMINAL_STATUSES = {"Kész", "Kiküldve", "Kihagyva"}
FINALIZED_STATUSES = {"Kész", "Kiküldve"}

_BELSOS_TIG_EMAIL_HTML = """\
<p>Kedves {nev},</p>
<p>
  Mellékelten küldjük a <b>{honap}</b> havi teljesítési igazolásodat.<br>
  Kérjük, ellenőrizd az adatokat, és jelezz vissza, ha bármi eltérést látsz.
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


def _belsos_employees(db: Session) -> list[Employee]:
    return db.query(Employee).filter(Employee.tipus == EmployeeType.BELSOS).order_by(Employee.full_name).all()


def _find(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate | None:
    return (
        db.query(InternalPerformanceCertificate)
        .filter(
            InternalPerformanceCertificate.employee_id == employee_id,
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
        )
        .first()
    )


def _get_or_create(db: Session, employee: Employee, ev: int, honap: int) -> InternalPerformanceCertificate:
    existing = _find(db, employee.id, ev, honap)
    if existing is not None:
        return existing
    record = InternalPerformanceCertificate(
        employee_id=employee.id,
        ev=ev,
        honap=honap,
        allapot="Készítés alatt",
        # A megbízás tárgya alapból a munkatárs adatlapjáról jön, de innentől
        # a TIG saját másolata - a felületen szabadon átírható anélkül, hogy
        # a személy törzsadata változna.
        megbizas_targya=employee.megbizas_targya,
        plusz_afa=employee.plusz_afa,
        # A teljesítés a hónapot KÖVETŐ hónapban történik (a hónap onnan
        # számolódik vissza) - alapból annak az első napja.
        teljesites_datuma=kovetkezo_honap_elseje(ev, honap),
    )
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


@router.get("/employee/{employee_id}", response_model=list[InternalPerformanceCertificateRead])
def list_for_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy munkatárs ÖSSZES belsős TIG-je, a legfrissebb hónappal elöl - ezt
    mutatja a személy adatlapján a "Belsős TIG-ek" szekció (havi bontásban az
    összeg, az állapot és a kiküldött igazolás linkje)."""
    return (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.employee_id == employee_id)
        .order_by(InternalPerformanceCertificate.ev.desc(), InternalPerformanceCertificate.honap.desc())
        .all()
    )


class TigDraftIn(BaseModel):
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    megjegyzes: str | None = None
    megbizas_targya: str | None = None
    teljesites_datuma: date | None = None
    keltezes: date | None = None


_DRAFT_FIELDS = (
    "netto_osszeg",
    "plusz_afa",
    "megjegyzes",
    "megbizas_targya",
    "teljesites_datuma",
    "keltezes",
)


def _apply_draft_fields(record: InternalPerformanceCertificate, payload: TigDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(record, field, value)


def _apply_teljesites_honap(db: Session, record: InternalPerformanceCertificate) -> None:
    """A teljesítés dátuma dönti el, melyik hónap TIG-je ez - mindig az azt
    MEGELŐZŐ hónap. Ha az admin olyan dátumot ad meg, ami másik hónapra
    mutat, a bejegyzés átkerül oda (a havi nézetben onnantól ott látszik).

    Ha a cél-hónapban már van TIG ugyanannak az embernek, nem írjuk felül -
    az adatbázis egyediség-megkötése (uq_internal_tig_employee_month) úgyis
    megakadályozná, csak nyers 500-zal; itt beszédes hibát adunk helyette."""
    if record.teljesites_datuma is None:
        return
    ev, honap = elozo_honap(record.teljesites_datuma)
    if (ev, honap) == (record.ev, record.honap):
        return
    utkozes = _find(db, record.employee_id, ev, honap)
    if utkozes is not None and utkozes.id != record.id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ehhez a teljesítési dátumhoz a(z) {ev_honap_szoveg(ev, honap)} hónap tartozna, "
                "de ott már van Belsős TIG ehhez a munkatárshoz."
            ),
        )
    record.ev = ev
    record.honap = honap


@router.post("/{employee_id}/{ev}/{honap}/save", response_model=InternalPerformanceCertificateRead)
def save_draft(
    employee_id: int,
    ev: int,
    honap: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    _apply_draft_fields(record, payload)
    _apply_teljesites_honap(db, record)
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/generalas-es-kuldes", response_model=InternalPerformanceCertificateRead)
def generate_and_send(
    employee_id: int,
    ev: int,
    honap: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Legenerálja a TIG dokumentumot a Google Docs sablonból, elmenti a
    Drive-ra, és PDF-ként kiküldi a munkatársnak emailben - ugyanaz a lépés,
    mint a Külsős TIG-nél (lásd performance_certificates.py generate_and_send),
    csak a belsős sablonnal és a hónap-alapú adatokkal.

    Sablon nélkül (nincs beállítva gdoc_belsos_tig_template_id) az email
    csatolmány nélkül megy ki - így a küldés akkor sem áll meg, ha a
    dokumentum-generálás nincs bekonfigurálva."""
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    _apply_draft_fields(record, payload)
    _apply_teljesites_honap(db, record)

    if not record.netto_osszeg or record.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    if not employee.email:
        raise HTTPException(status_code=400, detail=f"{employee.full_name} nem kapott email címet, így nem lehet kiküldeni a TIG-et.")

    keltezes = record.keltezes or date.today()
    record.keltezes = keltezes
    honap_szoveg = ev_honap_szoveg(record.ev, record.honap)

    doc_link = None
    pdf_bytes = None
    # A hónap a fájlnévben is betűvel: "2026_majus" helyett a teljes,
    # ékezetes alak megy, ahogy a dokumentumban is szerepel.
    base_name = f"{honap_szoveg}_{employee.full_name}_belsos_TIG"
    try:
        if settings.gdoc_belsos_tig_template_id:
            fields = {
                "nev": employee.full_name,
                "hely": employee.vallakozas_szekhely or "",
                "adoszam": employee.vallalkozas_adoszama or "",
                "targy": record.megbizas_targya or "",
                "honap": honap_szoveg,
                "tido": record.teljesites_datuma.strftime("%Y.%m.%d.") if record.teljesites_datuma else "",
                "netto": f"{record.netto_osszeg:,.0f}".replace(",", " "),
                "kelt": keltezes.strftime("%Y.%m.%d."),
                "afa": "+ ÁFA" if record.plusz_afa else "",
                "nettoki": szam_betukkel(record.netto_osszeg),
            }
            pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
                template_file_id=settings.gdoc_belsos_tig_template_id,
                base_name=base_name,
                fields=fields,
                output_folder_id=settings.drive_belsos_tig or settings.gdoc_output_folder_id or settings.drive_folder_id or None,
            )
            doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

        subject = f"{employee.full_name} - {honap_szoveg} havi teljesítési igazolás"
        html = _BELSOS_TIG_EMAIL_HTML.format(nev=employee.full_name, honap=honap_szoveg)
        send_message([employee.email], subject, html, pdf_bytes=pdf_bytes, pdf_filename=f"{base_name}.pdf")
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük el, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    record.allapot = "Kiküldve"
    record.file_url = doc_link
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
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    record.allapot = "Kihagyva"
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


def _get_finalized_or_404(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate:
    record = _find(db, employee_id, ev, honap)
    if record is None:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nem tartozik Belsős TIG bejegyzés.")
    if record.allapot not in FINALIZED_STATUSES:
        raise HTTPException(status_code=400, detail="Számla csak kiküldött Belsős TIG-hez tölthető fel.")
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
            megnevezes=f"Belsős TIG - {record.employee.full_name} - {ev_honap_szoveg(record.ev, record.honap)}",
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
