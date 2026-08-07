"""Van-e már TIG egy adott munkáról?

A TIG-ek TÉTELEKEN keresztül mondják meg, kinek a munkáját melyik projekten
igazolják (lásd models/performance_certificate.py PerformanceCertificateTetel):
egy TIG több ember és több projekt munkáját is lefedheti.

Van azonban egy visszafelé kompatibilis eset: az olyan TIG, aminek egyáltalán
NINCS tétele - ilyet a Notion-import és a kézi adatbázis-javítás is hagyhat
maga után. Az ilyen sor pontosan azt fedi, amiről a saját mezői szólnak: a
saját projektjén a saját emberét. Ezt a szabályt ez a modul tartja egy helyen,
hogy a szerződés-oldal és a TIG-oldal ugyanúgy lássa (különben egy import után
készült TIG "nem létezőnek" látszana, és a rendszer újra kérné)."""

from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel


def tetel_nelkuli(kifejezes=None):
    """SQL feltétel: ennek a TIG-nek nincs egyetlen tétele sem."""
    return ~PerformanceCertificate.tetelek.any()


def fedi_a_projektet(project_id: int):
    """SQL feltétel: ez a TIG érint egy adott projektet - tétellel vagy (tétel
    híján) a saját projektjén keresztül."""
    return or_(
        PerformanceCertificate.tetelek.any(PerformanceCertificateTetel.project_id == project_id),
        and_(PerformanceCertificate.project_id == project_id, tetel_nelkuli()),
    )


def fedi_a_munkat(project_id: int, employee_id: int):
    """SQL feltétel: ez a TIG egy konkrét ember konkrét projekten végzett
    munkájáról szól."""
    return or_(
        PerformanceCertificate.tetelek.any(
            and_(
                PerformanceCertificateTetel.project_id == project_id,
                PerformanceCertificateTetel.employee_id == employee_id,
            )
        ),
        and_(
            PerformanceCertificate.project_id == project_id,
            PerformanceCertificate.employee_id == employee_id,
            tetel_nelkuli(),
        ),
    )


def van_tig_a_munkara(db: Session, project_id: int, employee_id: int) -> bool:
    return db.query(PerformanceCertificate.id).filter(fedi_a_munkat(project_id, employee_id)).first() is not None
