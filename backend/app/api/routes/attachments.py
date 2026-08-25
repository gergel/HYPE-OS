"""Generikus fájl-csatolmány végpontok: szerződések, TIG-ek, számlák és egyéb
dokumentumok bármelyik rekordhoz. Minden fájl az R2 tárhelyre kerül (lásd
services/attachments.py) - a szolgáltatás lemezére semmi.

Egyetlen router szolgálja ki az összes entitást, mert a viselkedés mindenhol
ugyanaz. A jogosultság viszont entitásonként a SAJÁT oldaláé: egy projektkódhoz
csatolt számlát az tölthet fel, aki a Project Code-okat szerkesztheti (lásd
services/attachments.py ENTITAS_OLDALAK)."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import check_page_action, get_current_user
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee, van_szerepkore
from app.models.project_code import ProjectCode
from app.schemas.document_attachment import (
    DocumentAttachmentHataridoIn,
    DocumentAttachmentKifizetesIn,
    DocumentAttachmentRead,
)
from app.services import attachments, megrendeloi_szamla
from app.services.entity_registry import ENTITY_MODELS
from app.services.portal_storage import R2NotConfiguredError

router = APIRouter(prefix="/csatolmanyok", tags=["csatolmanyok"])


def _ellenoriz(db: Session, entity_type: str, entity_id: int) -> None:
    """Létező, csatolmányt fogadó entitás és létező rekord - enélkül egy
    kitalált entity_type-pal bárhova lehetne fájlt tölteni."""
    if entity_type not in attachments.ENTITAS_OLDALAK:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ehhez az entitáshoz nem csatolható fájl: {entity_type}")
    model = ENTITY_MODELS.get(entity_type)
    if model is None or db.get(model, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A rekord nem található")


def _jogosultsag(db: Session, user: Employee, entity_type: str, action: str) -> None:
    from app.core.security import DEFAULT_WRITE_ROLES

    if not van_szerepkore(user, *DEFAULT_WRITE_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nincs jogosultságod ehhez a művelethez")
    check_page_action(db, user, attachments.ENTITAS_OLDALAK[entity_type], action)


@router.get("/{entity_type}/{entity_id:int}", response_model=list[DocumentAttachmentRead])
def list_attachments(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    _ellenoriz(db, entity_type, entity_id)
    return attachments.list_for(db, entity_type, entity_id)


@router.post("/{entity_type}/{entity_id:int}", response_model=DocumentAttachmentRead)
async def upload_attachment(
    entity_type: str,
    entity_id: int,
    kategoria: str = Query("egyeb", description="szerzodes | tig | szamla | egyeb"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    _ellenoriz(db, entity_type, entity_id)
    _jogosultsag(db, user, entity_type, "edit")
    data = await file.read()
    try:
        rekord = attachments.save(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            kategoria=kategoria,
            filename=file.filename or "dokumentum",
            data=data,
            content_type=file.content_type,
        )
    except attachments.AttachmentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except R2NotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    db.commit()
    db.refresh(rekord)
    return rekord


@router.put("/{attachment_id:int}/fizetesi-allapot", response_model=DocumentAttachmentRead)
def set_fizetesi_hatarido(
    attachment_id: int,
    payload: DocumentAttachmentHataridoIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Egy feltöltött SZÁMLA fájl fizetési határideje - egyénileg, fájlonként
    (lásd models/document_attachment.py). Csak "szamla" kategóriájú
    csatolmányon értelmezhető: egy szerződés- vagy TIG-fájlnak nincs saját
    fizetési határideje.

    A KIFIZETÉS jelölése SZÁNDÉKOSAN nem itt megy: az bevétel-sort is nyit,
    ahhoz a POST .../kifizetve végpont kell (lásd
    services/megrendeloi_szamla.jelold_szamlat_kifizetettnek)."""
    rekord = db.get(DocumentAttachment, attachment_id)
    if rekord is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A csatolmány nem található")
    if rekord.kategoria != "szamla":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Csak számla kategóriájú fájlhoz állítható fizetési állapot.")
    _jogosultsag(db, user, rekord.entity_type, "edit")
    rekord.fizetesi_hatarido = payload.fizetesi_hatarido
    db.commit()
    db.refresh(rekord)
    return rekord


def _szamla_projektkodhoz(db: Session, user: Employee, attachment_id: int) -> tuple[DocumentAttachment, ProjectCode]:
    rekord = db.get(DocumentAttachment, attachment_id)
    if rekord is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A csatolmány nem található")
    if rekord.kategoria != "szamla" or rekord.entity_type != "projectCode":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Csak projektkódhoz tartozó számla fizethető ki itt.")
    _jogosultsag(db, user, rekord.entity_type, "edit")
    pk = db.get(ProjectCode, rekord.entity_id)
    if pk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A projektkód nem található")
    return rekord, pk


@router.post("/{attachment_id:int}/kifizetve", response_model=DocumentAttachmentRead)
def jelold_szamlat_kifizetettnek(
    attachment_id: int,
    payload: DocumentAttachmentKifizetesIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Egy konkrét feltöltött számla kifizetettnek jelölése - SAJÁT bevétel-
    sort nyit ennek a fájlnak az összegével (lásd
    services/megrendeloi_szamla.jelold_szamlat_kifizetettnek)."""
    rekord, pk = _szamla_projektkodhoz(db, user, attachment_id)
    try:
        rekord = megrendeloi_szamla.jelold_szamlat_kifizetettnek(
            db,
            rekord,
            pk,
            kifizetes_datuma=payload.kifizetes_datuma,
            netto=payload.netto,
            plusz_afa=payload.plusz_afa,
            fizetes_modja=payload.fizetes_modja,
            bevetelbe_ne_keruljon=payload.bevetelbe_ne_keruljon,
            kihagyas_oka=payload.kihagyas_oka,
        )
    except megrendeloi_szamla.SzamlaHiba as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    db.refresh(rekord)
    return rekord


@router.post("/{attachment_id:int}/kifizetve/visszavonas", response_model=DocumentAttachmentRead)
def vond_vissza_szamla_kifizetes(
    attachment_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """"Mégsincs kifizetve" - egy fájlonkénti kifizetés-jelölés visszavonása.
    A hozzá nyitott bevétel-sort nem törli, csak a dátumát veszi ki (lásd
    services/megrendeloi_szamla.vond_vissza_szamla_kifizetes)."""
    rekord, _pk = _szamla_projektkodhoz(db, user, attachment_id)
    rekord = megrendeloi_szamla.vond_vissza_szamla_kifizetes(db, rekord)
    db.commit()
    db.refresh(rekord)
    return rekord


@router.delete("/{attachment_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    rekord = db.get(DocumentAttachment, attachment_id)
    if rekord is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A csatolmány nem található")
    if rekord.entity_type not in attachments.ENTITAS_OLDALAK:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ismeretlen entitás")
    _jogosultsag(db, user, rekord.entity_type, "delete")
    try:
        attachments.delete(db, rekord)
    except R2NotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    db.commit()
