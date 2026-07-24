"""Megrendelői szerződés - a SubcontractorContractManager (alvállalkozói
oldal) párja a megrendelő (Client) oldalon: minden Project Code-hoz kell
tartoznia egy szerződésnek (ProjectCode.contract_id) - ha a megrendelőnek
már van álló keretszerződése, azt újra lehet használni, ha nincs, egy új
(erre a Project Code-ra szóló, "eseti") szerződést kell felvinni (lásd spec
3.1). Nincs Google Docs sablon-generálás/automata email ehhez (nincs
konfigurált gdoc template id a megrendelői szerződéshez, szemben az
alvállalkozói/TIG folyamatokkal) - a tényleges dokumentumot admin tölti fel
kézzel (szamla_url-hoz hasonló minta, lásd /fajl végpont), itt csak az
állapotot és a Project Code <-> Contract összerendelést kezeljük."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import Contract, ContractType
from app.models.employee import Employee
from app.models.project_code import ProjectCode
from app.schemas.contract import ContractRead
from app.services import document_storage

router = APIRouter(prefix="/megrendeloi-szerzodesek", tags=["client-contracts"])

PAGE = "/projektek/project-kodok"


def _get_project_code_or_404(db: Session, project_code_id: int) -> ProjectCode:
    pc = db.get(ProjectCode, project_code_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Project Code nem található")
    return pc


def _existing_keretszerzodes(db: Session, client_id: int) -> Contract | None:
    """A megrendelő már meglévő, bármelyik Project Code-jához kapcsolt
    keretszerződése, ha van - ha igen, egy új Project Code ehhez is
    hozzárendelhető anélkül, hogy új szerződést kellene felvinni."""
    return (
        db.query(Contract)
        .filter(Contract.client_id == client_id, Contract.tipus == ContractType.KERETSZERZODES)
        .first()
    )


class PendingProjectCode(BaseModel):
    project_code_id: int
    projektkod: str
    client_id: int
    client_nev: str | None
    existing_keretszerzodes_id: int | None


@router.get("", response_model=list[PendingProjectCode])
def list_pending(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Azok a Project Code-ok, amikhez még nincs szerződés rendelve
    (contract_id IS NULL) - mindegyiknél jelezzük, ha a megrendelőnek már van
    újrafelhasználható keretszerződése."""
    pending = db.query(ProjectCode).filter(ProjectCode.contract_id.is_(None)).all()
    result: list[PendingProjectCode] = []
    for pc in pending:
        existing = _existing_keretszerzodes(db, pc.client_id)
        result.append(
            PendingProjectCode(
                project_code_id=pc.id,
                projektkod=pc.projektkod,
                client_id=pc.client_id,
                client_nev=pc.client.nev if pc.client else None,
                existing_keretszerzodes_id=existing.id if existing else None,
            )
        )
    return result


@router.post("/{project_code_id}/use-existing/{contract_id}", response_model=ContractRead)
def use_existing_keretszerzodes(
    project_code_id: int,
    contract_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    pc = _get_project_code_or_404(db, project_code_id)
    contract = db.get(Contract, contract_id)
    if contract is None or contract.tipus != ContractType.KERETSZERZODES or contract.client_id != pc.client_id:
        raise HTTPException(status_code=400, detail="Ez a szerződés nem ehhez a megrendelőhöz tartozó keretszerződés.")
    pc.contract_id = contract.id
    db.commit()
    db.refresh(contract)
    return ContractRead.model_validate(contract)


class ClientContractIn(BaseModel):
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    keltezes: str | None = None


@router.post("/{project_code_id}/create", response_model=ContractRead)
def create_client_contract(
    project_code_id: int,
    payload: ClientContractIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    pc = _get_project_code_or_404(db, project_code_id)
    if pc.contract_id is not None:
        raise HTTPException(status_code=400, detail="Ehhez a Project Code-hoz már tartozik szerződés.")
    contract = Contract(
        tipus=ContractType.KERETSZERZODES,
        client_id=pc.client_id,
        ceg_neve=payload.ceg_neve or (pc.client.nev if pc.client else None),
        szekhely=payload.szekhely,
        adoszam=payload.adoszam,
        megbizas_targya=payload.megbizas_targya,
        szerzodes_allapota="Készítés alatt",
    )
    db.add(contract)
    db.flush()
    pc.contract_id = contract.id
    db.commit()
    db.refresh(contract)
    return ContractRead.model_validate(contract)


@router.post("/{project_code_id}/fajl", response_model=ContractRead)
async def upload_szerzodes_fajl(
    project_code_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A (aláírt) szerződés dokumentum feltöltése - feltöltés után a
    szerzodes_allapota automatikusan 'Kiküldve'-re vált, mert a dokumentum
    megléte jelenti, hogy a szerződés ténylegesen létrejött/kiküldésre
    került."""
    pc = _get_project_code_or_404(db, project_code_id)
    if pc.contract_id is None:
        raise HTTPException(status_code=400, detail="Előbb hozz létre (vagy válassz) szerződést ehhez a Project Code-hoz.")
    contract = db.get(Contract, pc.contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="A kapcsolt szerződés nem található")
    filename = file.filename or "szerzodes"
    ext = os.path.splitext(filename)[1]
    key = f"megrendeloi-szerzodes/{project_code_id}{ext}"
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    url = document_storage.upload_bytes(data, key, content_type)
    contract.szerzodes_file_url = url
    contract.szerzodes_allapota = "Kiküldve"
    db.commit()
    db.refresh(contract)
    return ContractRead.model_validate(contract)
