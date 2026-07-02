"""Automation modul - a 7 dokumentum-generáló Railway-klón helyett egyetlen,
paraméterezett szolgáltatás. A tényleges PDF/Storage/Email integráció a Fázis 3
munka része (lásd hype_os_build_roadmap.md) - itt a végleges API-alak és a
Timeline Event rögzítés van lefektetve.
"""

from enum import StrEnum

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.timeline import TimelineEvent

router = APIRouter(prefix="/automation", tags=["automation"])


class DocumentKind(StrEnum):
    TIG_ALVALLALKOZO = "tig_alvallalkozo"
    TIG_BELSOS = "tig_belsos"
    TIG_MEGRENDELO = "tig_megrendelo"
    SZERZODES_KULSOS_ESETI = "szerzodes_kulsos_eseti"
    SZERZODES_ALVALLALKOZO_KERET = "szerzodes_alvallalkozo_keret"
    SZERZODES_MEGRENDELO_ESETI = "szerzodes_megrendelo_eseti"
    SZERZODES_MEGRENDELO_KERET = "szerzodes_megrendelo_keret"


class GenerateDocumentRequest(BaseModel):
    entity_type: str
    entity_id: int
    document_kind: DocumentKind


class GenerateDocumentResponse(BaseModel):
    status: str
    document_kind: DocumentKind
    entity_type: str
    entity_id: int


@router.post(
    "/generate-document",
    response_model=GenerateDocumentResponse,
    dependencies=[Depends(require_roles(Role.ADMIN, Role.OPERATOR))],
)
def generate_document(payload: GenerateDocumentRequest, db: Session = Depends(get_db)):
    """generate_document(entity_type, entity_id, document_kind) pipeline belépési pontja:
    sablon kiválasztás -> PDF generálás -> R2 feltöltés -> email -> entitás frissítés -> Timeline Event.
    A PDF/Storage/Email lépések még nincsenek bekötve (Fázis 3) - egyelőre csak a Timeline
    Event rögzítése történik meg, hogy a modul API-szerződése stabil legyen.
    """
    event = TimelineEvent(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        event_type=f"document_requested:{payload.document_kind.value}",
        payload={"document_kind": payload.document_kind.value},
    )
    db.add(event)
    db.commit()

    return GenerateDocumentResponse(
        status="queued",
        document_kind=payload.document_kind,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
