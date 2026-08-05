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
from app.models.employee_monthly_item import (
    TETEL_TIPUSOK,
    TIPUS_SORREND,
    EmployeeMonthlyItem,
    elojeles_osszeg,
)
from app.models.finance import Expense
from app.models.internal_performance_certificate import (
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.schemas.internal_performance_certificate import InternalPerformanceCertificateRead
from app.services import document_storage
from app.services.gdoc_template import gdoc_fill_export_and_store_pdf
from app.services.google_email import send_message
from app.services.hu_datum import elozo_honap, ev_honap_szoveg, honap_neve, kovetkezo_honap_elseje
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
    # A munkatárs adatlapjáról jövő előtöltés: a TIG űrlap ezekkel indul, ha
    # még nincs bejegyzés arra a hónapra (olyankor `record` üres, tehát nem
    # lenne miből kitölteni).
    megbizas_targya: str | None
    plusz_afa: bool | None
    record: InternalPerformanceCertificateRead | None
    #: A hónap tételei (alapbér + extrák), amikből a TIG összege összeáll -
    #: lásd models/employee_monthly_item.py. Így a TIG készítője látja, MIÉRT
    #: annyi az összeg, nem csak azt, hogy mennyi.
    tetelek: list["HaviTetelRead"] = []


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

    tetelek = (
        db.query(EmployeeMonthlyItem)
        .filter(
            EmployeeMonthlyItem.ev == ev,
            EmployeeMonthlyItem.honap == honap,
            EmployeeMonthlyItem.employee_id.in_([e.id for e in employees]),
        )
        .all()
    )
    tetelek = sorted(tetelek, key=lambda t: (TIPUS_SORREND.get(t.tipus, 9), t.id))
    tetel_lookup: dict[int, list[HaviTetelRead]] = {}
    for tetel in tetelek:
        tetel_lookup.setdefault(tetel.employee_id, []).append(_tetel_kimenet(tetel))

    return [
        MonthEmployeeInfo(
            id=e.id,
            full_name=e.full_name,
            email=e.email,
            megbizas_targya=e.megbizas_targya,
            plusz_afa=e.plusz_afa,
            record=InternalPerformanceCertificateRead.model_validate(lookup[e.id]) if e.id in lookup else None,
            tetelek=tetel_lookup.get(e.id, []),
        )
        for e in employees
    ]


class HaviTeendo(BaseModel):
    """Egy konkrét ember konkrét hiányossága egy hónapban - ebből derül ki,
    KINEK MIT kell még elkészítenie."""

    employee_id: int
    full_name: str
    allapot: str | None
    #: Emberi mondat, hogy mi hiányzik (pl. "Nincs elkezdve", "Számla hiányzik").
    hianyzik: str


class HaviOsszesito(BaseModel):
    """Egy hónap "mappája": kész van-e, és ha nem, mi hiányzik belőle."""

    ev: int
    honap: int
    honap_szoveg: str
    #: A hónap TIG-jeit a KÖVETKEZŐ hónap első napján kell teljesíteni - ez a
    #: határidő (ugyanaz a dátum, amit a TIG teljesítési dátuma alapból kap).
    hatarido: date
    #: Lejárt-e a határidő úgy, hogy még maradt teendő.
    keses: bool
    #: nincs_elkezdve | folyamatban | tig_kesz | lezarva
    allapot: str
    osszes: int
    kesz: int
    kihagyva: int
    hianyzo: int
    brutto_osszesen: float | None
    teendok: list[HaviTeendo]


def _honap_teendoje(record: InternalPerformanceCertificate | None) -> str | None:
    """Mi hiányzik még ehhez az emberhez ebben a hónapban? None = kész."""
    if record is None:
        return "Nincs elkezdve"
    if record.allapot == "Kihagyva":
        return None
    if record.allapot not in FINALIZED_STATUSES:
        if record.netto_osszeg is None:
            return "Készítés alatt – összeg nincs megadva"
        return "Készítés alatt – még nincs kiküldve"
    if not record.invoices:
        return "Számla hiányzik"
    if not record.szamla_kifizetve:
        return "Kifizetés hiányzik"
    return None


@router.get("/attekintes", response_model=list[HaviOsszesito])
def havi_attekintes(
    honapok: int = 12,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """HAVI ÁTTEKINTÉS ("mappázás"): hónaponként külön, hogy melyik hónap van
    kész, és ahol nincs, ott pontosan kinek mi hiányzik - anélkül, hogy a
    hónapok összefolynának.

    A hónap akkor "lezárva", ha minden belsős munkatársnak vagy kiküldött
    TIG-je van feltöltött ÉS kifizetett számlával, vagy ki lett hagyva. A
    köztes állapot a "tig_kesz": a TIG-ek elkészültek, de a számla/kifizetés
    még hátravan.

    Azok a hónapok jelennek meg, amikre már van bejegyzés, plusz az utolsó
    `honapok` hónap - hogy a még el sem kezdett hónapok is látszódjanak,
    ne csak azok, amikhez valaki már hozzányúlt."""
    today = date.today()
    employees = _belsos_employees(db)

    records = db.query(InternalPerformanceCertificate).all()
    honap_szerint: dict[tuple[int, int], list[InternalPerformanceCertificate]] = {}
    for r in records:
        honap_szerint.setdefault((r.ev, r.honap), []).append(r)

    # Az utolsó N hónap (a folyó hónappal együtt) + minden olyan hónap, amiben
    # már van bejegyzés.
    honap_kulcsok: set[tuple[int, int]] = set(honap_szerint.keys())
    ev, honap = today.year, today.month
    for _ in range(max(honapok, 1)):
        honap_kulcsok.add((ev, honap))
        ev, honap = elozo_honap(date(ev, honap, 1))

    # A legelső bejegyzésnél RÉGEBBI hónapokat elhagyjuk: azok a rendszer
    # használatba vétele előttiek, örökre "hiányosnak" látszanának, és csak
    # elfednék az igazi teendőket. (Ha még egyetlen bejegyzés sincs, marad az
    # utolsó N hónap - egy friss rendszeren pont azokkal kell kezdeni.)
    if honap_szerint:
        legkorabbi = min(honap_szerint)
        honap_kulcsok = {k for k in honap_kulcsok if k >= legkorabbi}

    eredmeny: list[HaviOsszesito] = []
    for kulcs in sorted(honap_kulcsok, reverse=True):
        ev, honap = kulcs
        sorok = {r.employee_id: r for r in honap_szerint.get(kulcs, [])}
        # A jelenlegi belsősök MELLETT azok is beleszámítanak, akiknek erre a
        # hónapra van bejegyzésük, de azóta már nem belsősök - különben a
        # munkájuk (és az összegük) eltűnne a hónap összesítéséből.
        emberek = list(employees)
        ismert = {e.id for e in emberek}
        for employee_id in sorok:
            if employee_id not in ismert:
                korabbi = db.get(Employee, employee_id)
                if korabbi is not None:
                    emberek.append(korabbi)

        teendok: list[HaviTeendo] = []
        kesz = kihagyva = 0
        brutto = 0.0
        van_brutto = False
        for e in emberek:
            record = sorok.get(e.id)
            if record is not None:
                # A bruttó a séma számított mezője (nettó + ÁFA, ha kell) -
                # szándékosan onnan vesszük, hogy a képlet egy helyen legyen.
                osszeg = InternalPerformanceCertificateRead.model_validate(record).brutto_osszeg
                if osszeg is not None:
                    brutto += float(osszeg)
                    van_brutto = True
            hianyzik = _honap_teendoje(record)
            if hianyzik is None:
                if record is not None and record.allapot == "Kihagyva":
                    kihagyva += 1
                else:
                    kesz += 1
                continue
            teendok.append(
                HaviTeendo(
                    employee_id=e.id,
                    full_name=e.full_name,
                    allapot=record.allapot if record is not None else None,
                    hianyzik=hianyzik,
                )
            )

        hatarido = kovetkezo_honap_elseje(ev, honap)
        van_bejegyzes = bool(sorok)
        if not teendok:
            allapot = "lezarva"
        elif not van_bejegyzes:
            allapot = "nincs_elkezdve"
        elif all(t.hianyzik in ("Számla hiányzik", "Kifizetés hiányzik") for t in teendok):
            allapot = "tig_kesz"
        else:
            allapot = "folyamatban"

        eredmeny.append(
            HaviOsszesito(
                ev=ev,
                honap=honap,
                honap_szoveg=ev_honap_szoveg(ev, honap),
                hatarido=hatarido,
                keses=bool(teendok) and today > hatarido,
                allapot=allapot,
                osszes=len(emberek),
                kesz=kesz,
                kihagyva=kihagyva,
                hianyzo=len(teendok),
                brutto_osszesen=brutto if van_brutto else None,
                teendok=sorted(teendok, key=lambda t: t.full_name),
            )
        )
    return eredmeny


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
    """A csatolt belsős-TIG program (belsos-TIG-main) menete, egy az egyben:
    a Google Docs sablon másolása, a {{placeholder}}-ek cseréje, PDF export, a
    PDF feltöltése a Drive célmappába, az ideiglenes Doc törlése, végül az
    email a munkatársnak - a PDF csatolmánnyal. A Drive-ra feltöltött PDF
    linkje kerül a rekordba (file_url), tehát a rendszerben tárolt hivatkozás
    a KÉSZ igazolásra mutat, nem egy szerkeszthető dokumentumra.

    Sablon nélkül nem küldünk: egy PDF nélküli TIG-email nem ér semmit, ezért
    inkább beszédes hibát adunk a hiányzó beállítás nevével."""
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
    if not settings.belsos_tig_template_id:
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=(
                "Nincs beállítva a Belsős TIG dokumentum-sablon, így a PDF nem generálható. "
                "Állítsd be a GDOC_BELSOS_TIG_TEMPLATE_ID (vagy GOOGLE_DRIVE_TEMPLATE_ID) "
                "környezeti változót a backendhez."
            ),
        )

    keltezes = record.keltezes or date.today()
    record.keltezes = keltezes
    honap_szoveg = ev_honap_szoveg(record.ev, record.honap)
    # Fájlnév és tárgy az eredeti program formátumában ("2026. május_Név_TIG").
    base_name = f"{honap_szoveg}_{employee.full_name}_TIG"

    fields = {
        "nev": employee.full_name,
        "hely": employee.vallakozas_szekhely or "",
        "adoszam": employee.vallalkozas_adoszama or "",
        "targy": record.megbizas_targya or "",
        # Az eredeti sablonban a {{tido}} a HÓNAP szövege (nem a teljesítés
        # napja) - a teljesítés dátuma csak a hónap kiszámolására szolgál.
        "tido": honap_szoveg,
        "honap": honap_szoveg,
        # Ezres elválasztó ponttal, ahogy az eredeti program írja: "120.000".
        "netto": f"{record.netto_osszeg:,.0f}".replace(",", "."),
        "kelt": keltezes.strftime("%Y.%m.%d."),
        "afa": "+ ÁFA" if record.plusz_afa else "",
        "nettoki": szam_betukkel(record.netto_osszeg),
    }

    try:
        pdf_bytes, pdf_link = gdoc_fill_export_and_store_pdf(
            template_file_id=settings.belsos_tig_template_id,
            base_name=base_name,
            fields=fields,
            output_folder_id=settings.belsos_tig_folder_id or None,
        )
        subject = f"{employee.full_name}_{honap_szoveg} - hónap_TIG"
        html = _BELSOS_TIG_EMAIL_HTML.format(nev=employee.full_name, honap=honap_szoveg)
        send_message([employee.email], subject, html, pdf_bytes=pdf_bytes, pdf_filename=f"{base_name}.pdf")
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük el, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    record.allapot = "Kiküldve"
    record.file_url = pdf_link
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


class AllapotIn(BaseModel):
    allapot: str


ALLOWED_STATUSES = ["Készítés alatt", "Kiküldve", "Kihagyva"]


@router.post("/{employee_id}/{ev}/{honap}/allapot", response_model=InternalPerformanceCertificateRead)
def set_allapot(
    employee_id: int,
    ev: int,
    honap: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A TIG állapotának KÉZI átállítása. Aki az oldalon szerkeszthet, itt is
    javíthat: pl. visszavehet egy tévesen kiküldöttre állított TIG-et, vagy
    kiküldöttnek jelölhet egyet, amit a rendszeren kívül küldtek el. A
    generálás/küldés folyamat változatlan - ez csak az állapot javítása."""
    if payload.allapot not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Ismeretlen állapot. Választható: {', '.join(ALLOWED_STATUSES)}")
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    record.allapot = payload.allapot
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


# ─────────────────────────────────────────────────────────────────────────────
# Havi tételek: az alapbér és a hozzáadódó extrák
#
# Miért nem elég a TIG egyetlen "nettó összeg" mezője: az összeg hónap közben,
# darabonként áll össze (alapbér + túlóra + benzin + étkezés…), gyakran más
# ember viszi fel, mint aki majd a TIG-et elkészíti. Ha csak egy szám lenne, a
# TIG készítőjének kellene fejben összeadnia - és nem is látná, mi miből jött.
# Ezért a tételek a forrás, a TIG összege pedig belőlük SZÁMOLÓDIK.
# ─────────────────────────────────────────────────────────────────────────────


class HaviTetelIn(BaseModel):
    tipus: str = "extra"
    megnevezes: str
    osszeg: float = 0
    project_code_id: int | None = None
    #: A tétel pontos napja (pl. mikor volt a túlóra, mikor vonták le).
    #: SZÁNDÉKOSAN nem befolyásolja, melyik hónaphoz tartozik a tétel: azt
    #: kizárólag az URL-ben megadott (ev, honap) dönti el. Így egy hónap végi
    #: elszámolásba be lehet tenni egy más napra eső tételt is anélkül, hogy
    #: átugrana egy másik hónapba.
    datum: date | None = None
    megjegyzes: str | None = None


class HaviTetelPatch(BaseModel):
    """Részleges módosítás: CSAK a ténylegesen elküldött mezőket írjuk át.

    Külön séma a felvitelitől, mert ott minden mező kötelező. Ha itt is a
    felviteli sémát használnánk, egy "csak az összeget írom át" kérés némán
    törölné a tétel projektkódját és dátumát - a hiányzó mező ugyanis
    None-ként érkezne."""

    tipus: str | None = None
    megnevezes: str | None = None
    osszeg: float | None = None
    project_code_id: int | None = None
    datum: date | None = None
    megjegyzes: str | None = None


class HaviTetelRead(BaseModel):
    id: int
    employee_id: int
    ev: int
    honap: int
    tipus: str
    megnevezes: str
    osszeg: float
    project_code_id: int | None = None
    projektkod: str | None = None
    datum: date | None = None
    megjegyzes: str | None = None

    model_config = {"from_attributes": True}


def _tetel_kimenet(tetel: EmployeeMonthlyItem) -> HaviTetelRead:
    adat = HaviTetelRead.model_validate(tetel)
    adat.projektkod = tetel.project_code.projektkod if tetel.project_code else None
    return adat


def _honap_tetelei(db: Session, employee_id: int, ev: int, honap: int) -> list[EmployeeMonthlyItem]:
    sorok = (
        db.query(EmployeeMonthlyItem)
        .filter(
            EmployeeMonthlyItem.employee_id == employee_id,
            EmployeeMonthlyItem.ev == ev,
            EmployeeMonthlyItem.honap == honap,
        )
        .all()
    )
    # Alapbér -> extrák -> levonandók, típuson belül felvitel szerint: így a
    # lista úgy olvasható, ahogy az összeg összeáll (lásd TIPUS_SORREND).
    return sorted(sorok, key=lambda t: (TIPUS_SORREND.get(t.tipus, 9), t.id))


def _tiltsd_ha_lezart(db: Session, employee_id: int, ev: int, honap: int) -> None:
    """Véglegesített (kiküldött/kész/kihagyott) hónaphoz nem lehet tételt
    felvinni, módosítani vagy törölni.

    Azért tiltás és nem "csendben engedjük", mert az egész szerkezet azon áll,
    hogy A TÉTELEK ÖSSZEGE = A TIG ÖSSZEGE. Egy kiküldött igazolás összegét
    utólag nem írhatjuk át, tehát ha a tételt mégis engednénk, a bontás és a
    kiküldött összeg némán szétcsúszna - és épp az lenne megtévesztő, amit ez
    a nézet meg akar mutatni. Egy később felmerülő költség a KÖVETKEZŐ hónapra
    vihető fel (vagy a hónap állapotát kell visszaállítani)."""
    record = _find(db, employee_id, ev, honap)
    if record is not None and record.allapot in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A(z) {ev_honap_szoveg(ev, honap)} hónap Belsős TIG-je már véglegesítve van "
                f'("{record.allapot}"), ezért a tételei nem módosíthatók. Vidd fel a következő '
                "hónapra, vagy állítsd vissza a hónap állapotát."
            ),
        )


def _ujraszamol_tig_osszeget(db: Session, employee: Employee, ev: int, honap: int) -> None:
    """A hónap TIG-jének nettó összege = a havi tételek összege.

    Ha még nincs TIG erre a hónapra, létrehozzuk (piszkozatként) - különben az
    első felvitt extra sehol nem látszódna."""
    tetelek = _honap_tetelei(db, employee.id, ev, honap)
    if not tetelek:
        return
    record = _get_or_create(db, employee, ev, honap)
    record.netto_osszeg = float(sum(elojeles_osszeg(t.tipus, t.osszeg) for t in tetelek))


@router.get("/{employee_id}/{ev}/{honap}/tetelek", response_model=list[HaviTetelRead])
def list_havi_tetelek(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    return [_tetel_kimenet(t) for t in _honap_tetelei(db, employee_id, ev, honap)]


@router.post("/{employee_id}/{ev}/{honap}/tetelek", response_model=HaviTetelRead)
def create_havi_tetel(
    employee_id: int,
    ev: int,
    honap: int,
    payload: HaviTetelIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    employee = _validate_belsos_employee(db, employee_id)
    _tiltsd_ha_lezart(db, employee_id, ev, honap)
    if payload.tipus not in TETEL_TIPUSOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen tétel-típus: {payload.tipus}")
    if payload.tipus == "alapber" and any(
        t.tipus == "alapber" for t in _honap_tetelei(db, employee_id, ev, honap)
    ):
        raise HTTPException(status_code=409, detail="Ehhez a hónaphoz már van alapbér felvéve.")

    tetel = EmployeeMonthlyItem(
        employee_id=employee_id,
        ev=ev,
        honap=honap,
        tipus=payload.tipus,
        megnevezes=payload.megnevezes.strip() or ("Alapbér" if payload.tipus == "alapber" else "Extra"),
        osszeg=payload.osszeg,
        project_code_id=payload.project_code_id,
        datum=payload.datum,
        megjegyzes=payload.megjegyzes,
    )
    db.add(tetel)
    db.flush()
    _ujraszamol_tig_osszeget(db, employee, ev, honap)
    db.commit()
    db.refresh(tetel)
    return _tetel_kimenet(tetel)


@router.patch("/tetelek/{tetel_id}", response_model=HaviTetelRead)
def update_havi_tetel(
    tetel_id: int,
    payload: HaviTetelPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    tetel = db.get(EmployeeMonthlyItem, tetel_id)
    if tetel is None:
        raise HTTPException(status_code=404, detail="A tétel nem található")
    _tiltsd_ha_lezart(db, tetel.employee_id, tetel.ev, tetel.honap)

    valtozok = payload.model_dump(exclude_unset=True)
    uj_tipus = valtozok.get("tipus")
    if uj_tipus is not None:
        if uj_tipus not in TETEL_TIPUSOK:
            raise HTTPException(status_code=400, detail=f"Ismeretlen tétel-típus: {uj_tipus}")
        # Alapbérből hónaponként csak egy lehet - ugyanaz a szabály, mint
        # felvitelnél; enélkül átminősítéssel meg lehetne kerülni.
        if uj_tipus == "alapber" and any(
            t.tipus == "alapber" and t.id != tetel.id
            for t in _honap_tetelei(db, tetel.employee_id, tetel.ev, tetel.honap)
        ):
            raise HTTPException(status_code=409, detail="Ehhez a hónaphoz már van alapbér felvéve.")

    # Csak a ténylegesen elküldött mezők - lásd HaviTetelPatch.
    for mezo, ertek in valtozok.items():
        if mezo == "megnevezes":
            ertek = (ertek or "").strip() or tetel.megnevezes
        # Az (ev, honap) SZÁNDÉKOSAN nincs a módosítható mezők közt: egy tétel
        # hovatartozását mindig a hónap-választás dönti el, nem a dátuma.
        setattr(tetel, mezo, ertek)
    db.flush()
    _ujraszamol_tig_osszeget(db, tetel.employee, tetel.ev, tetel.honap)
    db.commit()
    db.refresh(tetel)
    return _tetel_kimenet(tetel)


@router.delete("/tetelek/{tetel_id}", status_code=204)
def delete_havi_tetel(
    tetel_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    tetel = db.get(EmployeeMonthlyItem, tetel_id)
    if tetel is None:
        raise HTTPException(status_code=404, detail="A tétel nem található")
    _tiltsd_ha_lezart(db, tetel.employee_id, tetel.ev, tetel.honap)
    employee, ev, honap = tetel.employee, tetel.ev, tetel.honap
    db.delete(tetel)
    db.flush()
    _ujraszamol_tig_osszeget(db, employee, ev, honap)
    db.commit()


class HaviKoltseg(BaseModel):
    """Egy hónap: mibe került nekünk ez az ember."""

    ev: int
    honap: int
    honap_nev: str
    tig_id: int | None = None
    allapot: str | None = None
    netto_osszeg: float | None = None
    brutto_osszeg: float | None = None
    alapber: float = 0
    extra: float = 0
    #: A levonandó tételek összege POZITÍVAN - a nettó összegből már le van vonva.
    levonas: float = 0
    tetelek: list[HaviTetelRead] = []


class EvesKoltseg(BaseModel):
    ev: int
    osszesen: float
    honapok: list[HaviKoltseg]


class HonapReszletek(BaseModel):
    """Egy munkatárs EGY hónapja teljes egészében - ezt nyitja meg a saját
    oldala (lásd frontend app/(app)/belsos-tig/[employeeId]/[ev]/[honap])."""

    employee_id: int
    full_name: str
    ev: int
    honap: int
    honap_nev: str
    record: InternalPerformanceCertificateRead | None = None
    tetelek: list[HaviTetelRead] = []
    alapber: float = 0
    extra: float = 0
    #: A levonandó tételek összege POZITÍVAN; az `osszesen`-ből már levontuk.
    levonas: float = 0
    osszesen: float = 0


@router.get("/{employee_id}/{ev}/{honap}/reszletek", response_model=HonapReszletek)
def honap_reszletek(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy hónap teljes képe: az alapbér, a hozzáadott extrák, a szumma, és a
    hónap TIG-je (állapot, dokumentum, számlák).

    Az `osszesen` a TÉTELEK összege - ez az, ami a TIG-re kerül. Ha egy régi
    hónapnál nincsenek tételek (a tételes nyilvántartás előttről), a TIG-en
    rögzített nettó összeget adjuk vissza, hogy a nézet akkor se legyen üres."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")

    record = _find(db, employee_id, ev, honap)
    tetelek = _honap_tetelei(db, employee_id, ev, honap)
    alapber = float(sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "alapber"))
    extra = float(sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "extra"))
    levonas = float(sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "levonando"))
    olvasott = InternalPerformanceCertificateRead.model_validate(record) if record is not None else None

    return HonapReszletek(
        employee_id=employee_id,
        full_name=employee.full_name,
        ev=ev,
        honap=honap,
        honap_nev=honap_neve(honap),
        record=olvasott,
        tetelek=[_tetel_kimenet(t) for t in tetelek],
        alapber=alapber,
        extra=extra,
        levonas=levonas,
        osszesen=(
            alapber + extra - levonas
            if tetelek
            else float(olvasott.netto_osszeg or 0)
            if olvasott
            else 0
        ),
    )


@router.get("/employee/{employee_id}/koltsegek", response_model=list[EvesKoltseg])
def employee_koltsegek(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy munkatárs havi költségei ÉVEKRE csoportosítva, évente összesítve -
    ez válaszolja meg az adatlapon, hogy "mibe került nekünk ez az ember".

    Két forrásból áll össze, hónapra vetítve: a hónap Belsős TIG-je (ez a
    kifizetett összeg) és a hónaphoz rögzített tételek (ebből látszik, MIBŐL
    jött ki). Az évi összeg a TIG-ek nettó összege - a tételek ugyanazt az
    összeget bontják, nem jönnek hozzá még egyszer."""
    tigek = (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.employee_id == employee_id)
        .all()
    )
    tetelek = (
        db.query(EmployeeMonthlyItem).filter(EmployeeMonthlyItem.employee_id == employee_id).all()
    )

    honapok: dict[tuple[int, int], HaviKoltseg] = {}

    def _honap(ev: int, honap: int) -> HaviKoltseg:
        kulcs = (ev, honap)
        if kulcs not in honapok:
            honapok[kulcs] = HaviKoltseg(ev=ev, honap=honap, honap_nev=honap_neve(honap))
        return honapok[kulcs]

    for tig in tigek:
        adat = _honap(tig.ev, tig.honap)
        olvasott = InternalPerformanceCertificateRead.model_validate(tig)
        adat.tig_id = tig.id
        adat.allapot = tig.allapot
        adat.netto_osszeg = olvasott.netto_osszeg
        adat.brutto_osszeg = olvasott.brutto_osszeg

    for tetel in tetelek:
        adat = _honap(tetel.ev, tetel.honap)
        adat.tetelek.append(_tetel_kimenet(tetel))
        if tetel.tipus == "alapber":
            adat.alapber += float(tetel.osszeg or 0)
        elif tetel.tipus == "levonando":
            adat.levonas += float(tetel.osszeg or 0)
        else:
            adat.extra += float(tetel.osszeg or 0)

    evek: dict[int, list[HaviKoltseg]] = {}
    for adat in honapok.values():
        adat.tetelek.sort(key=lambda t: (TIPUS_SORREND.get(t.tipus, 9), t.id))
        evek.setdefault(adat.ev, []).append(adat)

    return [
        EvesKoltseg(
            ev=ev,
            osszesen=float(sum(h.netto_osszeg or 0 for h in sorted_honapok)),
            honapok=sorted_honapok,
        )
        for ev, sorted_honapok in (
            (ev, sorted(lista, key=lambda h: h.honap, reverse=True)) for ev, lista in evek.items()
        )
    ]
