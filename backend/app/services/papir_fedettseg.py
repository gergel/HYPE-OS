"""Van-e már PAPÍR egy adott munkáról - szerződésnél és TIG-nél egyformán.

Mind az eseti szerződés (models/contract.py ContractTetel), mind a TIG
(models/performance_certificate.py PerformanceCertificateTetel) TÉTELEKEN
keresztül mondja meg, kinek a munkáját melyik projekten fedi: egy papír több
ember és több projekt munkájáról is szólhat.

Egy visszafelé kompatibilis eset van: az olyan sor, aminek egyáltalán nincs
tétele - ilyet a Notion-import, a régi adat és a kézi adatbázis-javítás is
hagyhat maga után. Az ilyen sor pontosan azt fedi, amiről a saját mezői
szólnak: a saját projektjén a saját emberét. Ezt a szabályt tartja egy helyen
ez a modul, hogy a szerződés-oldal és a TIG-oldal ugyanúgy lássa (különben egy
import után készült papír "nem létezőnek" látszana, és a rendszer újra kérné).

A `fej` a Contract vagy a PerformanceCertificate osztály, a `tetel` a hozzá
tartozó tétel-osztály - mindkettőn `tetelek` a kapcsolat neve."""

from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session


def tetel_nelkuli(fej):
    """SQL feltétel: ennek a papírnak nincs egyetlen tétele sem."""
    return ~fej.tetelek.any()


def fedi_a_projektet(fej, tetel, project_id: int):
    """SQL feltétel: ez a papír érint egy adott projektet - tétellel vagy
    (tétel híján) a saját projektjén keresztül."""
    return or_(
        fej.tetelek.any(tetel.project_id == project_id),
        and_(fej.project_id == project_id, tetel_nelkuli(fej)),
    )


def fedi_a_munkat(fej, tetel, project_id: int, employee_id: int):
    """SQL feltétel: ez a papír egy konkrét ember konkrét projekten végzett
    munkájáról szól."""
    return or_(
        fej.tetelek.any(and_(tetel.project_id == project_id, tetel.employee_id == employee_id)),
        and_(
            fej.project_id == project_id,
            fej.employee_id == employee_id,
            tetel_nelkuli(fej),
        ),
    )


def van_papir_a_munkara(db: Session, fej, tetel, project_id: int, employee_id: int) -> bool:
    return db.query(fej.id).filter(fedi_a_munkat(fej, tetel, project_id, employee_id)).first() is not None
