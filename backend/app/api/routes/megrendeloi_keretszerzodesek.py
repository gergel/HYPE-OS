"""Megrendelői keretszerződések - akikkel KERETBEN dolgozunk.

Az adat már megvan: a Notion "Keretszerződés" adatbázisa a `Contract` táblába
importálódik `tipus=KERETSZERZODES` értékkel (lásd
notion_import/importers.import_contracts). Ami hiányzott, az a felület és a
kiküldés - ez a modul azt adja hozzá.

Miért nem a `contracts.py`-ban? Mert az az ALVÁLLALKOZÓI keretszerződéseké (a
crew felé), és a két oldal külön jogosultsághoz tartozik: a megrendelői
keretszerződés a projektkódokhoz kapcsolódik, nem a csapathoz.

Fontos, hogy a keretszerződés az ESETI szerződést váltja ki, a TIG-et NEM: a
keret arról szól, milyen feltételekkel dolgozunk együtt, a TIG arról, hogy egy
konkrét munka elkészült (lásd services/megrendeloi_papir.py).
"""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.client import Client
from app.models.contract import Contract, ContractType
from app.models.employee import Employee
from app.models.project_code import ProjectCode
from app.services import document_storage, notion_mapping
from app.services.megrendeloi_papir import megrendeloi_keret_ervenyes
from app.services.gdoc_template import gdoc_fill_export_and_store_pdf
from app.services.google_email import send_message

router = APIRouter(prefix="/megrendeloi-keretszerzodesek", tags=["megrendeloi-keretszerzodesek"])

PAGE = "/projektek/project-kodok"


class KeretRead(BaseModel):
    id: int
    client_id: int | None = None
    client_nev: str | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None
    megbizas_targya: str | None = None
    keltezes: date | None = None
    allapot: str | None = None
    file_url: str | None = None
    alairt_file_url: str | None = None
    alairva: bool = False
    #: Érvényes-e MA. Ettől függ, hogy kiváltja-e az eseti szerződést.
    ervenyes: bool = False
    #: Hány projektkódnál használjuk.
    projektkod_db: int = 0


class KeretIn(BaseModel):
    client_id: int | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None
    megbizas_targya: str | None = None
    keltezes: date | None = None


def _kimenet(c: Contract, projektkod_db: int = 0) -> KeretRead:
    return KeretRead(
        id=c.id,
        client_id=c.client_id,
        client_nev=c.client.nev if c.client else None,
        ceg_neve=c.ceg_neve,
        szekhely=c.szekhely,
        adoszam=c.adoszam,
        kepviselo=c.vallalkozas_kepviseloje,
        nyilvantartasi_szam=c.vallalkozas_nyilvantartasi_szam,
        email=c.email,
        megbizas_targya=c.megbizas_targya,
        keltezes=c.keltezes,
        allapot=c.szerzodes_allapota,
        file_url=c.szerzodes_file_url,
        alairt_file_url=c.alairt_file_url,
        alairva=bool(c.alairva),
        ervenyes=megrendeloi_keret_ervenyes(c),
        projektkod_db=projektkod_db,
    )


def _get_or_404(db: Session, keret_id: int) -> Contract:
    c = db.get(Contract, keret_id)
    if c is None or c.tipus != ContractType.KERETSZERZODES:
        raise HTTPException(status_code=404, detail="Ez a megrendelői keretszerződés nem található.")
    return c


@router.get("", response_model=list[KeretRead])
def list_keretszerzodesek(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az összes megrendelői keretszerződés, az élőkkel elöl."""
    sorok = db.scalars(
        select(Contract)
        .options(selectinload(Contract.client), selectinload(Contract.idoszakok))
        .where(Contract.tipus == ContractType.KERETSZERZODES)
    ).all()
    # A projektkódok számát EGY lekérdezésből vesszük - soronkénti count()
    # néhány tucat keretszerződésnél is fölöslegesen sok kört tenne.
    darabok = {
        contract_id: darab
        for contract_id, darab in db.execute(
            select(ProjectCode.contract_id, func.count(ProjectCode.id))
            .where(ProjectCode.contract_id.is_not(None))
            .group_by(ProjectCode.contract_id)
        ).all()
    }

    kimenet = [_kimenet(c, darabok.get(c.id, 0)) for c in sorok]
    kimenet.sort(key=lambda k: (not k.ervenyes, (k.ceg_neve or k.client_nev or "").casefold()))
    return kimenet


@router.post("", response_model=KeretRead, status_code=201)
def create_keretszerzodes(
    payload: KeretIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    if not (payload.ceg_neve or "").strip() and payload.client_id is None:
        raise HTTPException(status_code=400, detail="Add meg a céget vagy az ügyfelet.")
    if payload.client_id is not None and db.get(Client, payload.client_id) is None:
        raise HTTPException(status_code=404, detail="Ez az ügyfél nem található.")
    c = Contract(
        tipus=ContractType.KERETSZERZODES,
        # A `keretszerzodes` jelölő nélkül a sor nem számítana valódi
        # keretszerződésnek (lásd models/contract.megkotott_keretszerzodes).
        keretszerzodes=True,
        client_id=payload.client_id,
        ceg_neve=payload.ceg_neve,
        szekhely=payload.szekhely,
        adoszam=payload.adoszam,
        vallalkozas_kepviseloje=payload.kepviselo,
        vallalkozas_nyilvantartasi_szam=payload.nyilvantartasi_szam,
        email=payload.email,
        megbizas_targya=payload.megbizas_targya,
        keltezes=payload.keltezes,
        szerzodes_allapota="Készítés alatt",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _kimenet(c)


@router.patch("/{keret_id}", response_model=KeretRead)
def update_keretszerzodes(
    keret_id: int,
    payload: KeretIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    c = _get_or_404(db, keret_id)
    mezok = {
        "kepviselo": "vallalkozas_kepviseloje",
        "nyilvantartasi_szam": "vallalkozas_nyilvantartasi_szam",
    }
    for mezo, ertek in payload.model_dump(exclude_unset=True).items():
        setattr(c, mezok.get(mezo, mezo), ertek)
    db.commit()
    db.refresh(c)
    return _kimenet(c)


_EMAIL_HTML = """\
<p>Kedves Partnerünk!</p>
<p>Mellékelten küldjük a keretszerződésünket.<br>
Kérjük, ellenőrizzék az adatokat, és aláírva szíveskedjenek visszaküldeni.</p>
<p>Köszönettel,<br>HYPE Productions Kft.</p>
"""


@router.post("/{keret_id}/generalas-es-kuldes", response_model=KeretRead)
def generate_and_send(
    keret_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A keretszerződés generálása a sablonból és kiküldése.

    A placeholder-nevek a csatolt megrendelo-keretszerzodes programból jönnek
    (nev / hely / adoszam / targy / kelt / nyilvszam / kepvis), tehát a MEGLÉVŐ
    Google Docs sablon változtatás nélkül használható."""
    c = _get_or_404(db, keret_id)
    if not c.email:
        raise HTTPException(status_code=400, detail="Nincs e-mail cím, így nem lehet kiküldeni a keretszerződést.")
    if not settings.gdoc_megrendeloi_keret_template_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "Nincs beállítva a megrendelői keretszerződés sablonja. Állítsd be a "
                "GDOC_MEGRENDELOI_KERET_TEMPLATE_ID környezeti változót a backendhez."
            ),
        )
    c.keltezes = c.keltezes or date.today()
    nev = c.ceg_neve or (c.client.nev if c.client else "megrendelo")
    base_name = f"{nev}_keretszerzodes"
    try:
        pdf_bytes, pdf_link = gdoc_fill_export_and_store_pdf(
            template_file_id=settings.gdoc_megrendeloi_keret_template_id,
            base_name=base_name,
            fields={
                "nev": nev,
                "hely": c.szekhely or "",
                "adoszam": c.adoszam or "",
                "targy": c.megbizas_targya or "",
                "kelt": c.keltezes.strftime("%Y.%m.%d.") if c.keltezes else "",
                "nyilvszam": c.vallalkozas_nyilvantartasi_szam or "",
                "kepvis": c.vallalkozas_kepviseloje or "",
            },
            output_folder_id=settings.gdoc_keretszerzodes_folder_id or settings.gdoc_output_folder_id or None,
        )
        send_message([c.email], f"{nev} – keretszerződés", _EMAIL_HTML, pdf_bytes=pdf_bytes,
                     pdf_filename=f"{base_name}.pdf")
    except RuntimeError as exc:
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    c.szerzodes_allapota = "Kiküldve"
    c.szerzodes_file_url = pdf_link
    db.commit()
    db.refresh(c)
    return _kimenet(c)


async def _fajl_feltoltes(db: Session, c: Contract, file: UploadFile, *, alairt: bool) -> None:
    """Saját vagy aláírt példány feltöltése.

    Mindkét ágon ugyanaz a menet, csak más mezőpárba ír - és a régi objektumot
    CSAK a sikeres mentés után dobjuk el, hogy egy elhasalt feltöltésnél ne
    maradjunk se régi, se új fájllal."""
    data = await file.read()
    kiterjesztes = os.path.splitext(file.filename or "")[1] or ".pdf"
    kulcs = f"megrendelo-keret{'-alairt' if alairt else ''}/{c.id}{kiterjesztes}"
    regi = c.alairt_file_storage_key if alairt else c.szerzodes_file_storage_key
    url = document_storage.upload_bytes(data, kulcs, file.content_type or "application/octet-stream")
    if alairt:
        c.alairt_file_url, c.alairt_file_storage_key = url, kulcs
        c.alairva = True
    else:
        c.szerzodes_file_url, c.szerzodes_file_storage_key = url, kulcs
        if c.szerzodes_allapota != "Kiküldve":
            c.szerzodes_allapota = "Kiküldve"
    db.commit()
    if regi and regi != kulcs:
        document_storage.delete_object(regi)


@router.post("/{keret_id}/sajat-fajl", response_model=KeretRead)
async def upload_sajat(
    keret_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """SAJÁT keretszerződés feltöltése a generálás helyett - van, amit a
    megrendelő ad a saját sablonjával, és van, ami régebbi, a rendszer előtti."""
    c = _get_or_404(db, keret_id)
    await _fajl_feltoltes(db, c, file, alairt=False)
    db.refresh(c)
    return _kimenet(c)


@router.post("/{keret_id}/alairt-fajl", response_model=KeretRead)
async def upload_alairt(
    keret_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    c = _get_or_404(db, keret_id)
    await _fajl_feltoltes(db, c, file, alairt=True)
    db.refresh(c)
    return _kimenet(c)


@router.delete("/{keret_id}", status_code=204)
def delete_keretszerzodes(
    keret_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Csak akkor törölhető, ha nem hivatkozik rá projektkód - különben a
    projektkód szerződés nélkül maradna, némán."""
    c = _get_or_404(db, keret_id)
    if db.scalars(select(ProjectCode.id).where(ProjectCode.contract_id == c.id)).first():
        raise HTTPException(
            status_code=400,
            detail="Ez a keretszerződés projektkódokhoz van kapcsolva - előbb azokat kell leoldani róla.",
        )
    kulcsok = [k for k in (c.szerzodes_file_storage_key, c.alairt_file_storage_key) if k]
    # A Notion-leképezés is menjen vele: enélkül ez a keretszerződés soha többé
    # nem tudna visszaimportálódni a Notionból (lásd services/notion_mapping.py).
    notion_mapping.torold_a_leképezest(db, "Contract", c.id)
    db.delete(c)
    db.commit()
    for k in kulcsok:
        document_storage.delete_object(k)
