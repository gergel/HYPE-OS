"""Egy Kiadás (Expense) sor törlésekor mi történjen azzal, ami rá hivatkozik.

Egy kiadás nem magányos sor: a TIG-ek "kifizetve" jelölése HOZZA LÉTRE
(lásd routes/performance_certificates.py és
internal_performance_certificates.py), a Notionból hozott havi tételek pedig
ugyanazt a költséget írják le a munkatárs oldaláról. Mindegyik idegen kulccsal
mutat az `expenses` sorra.

Enélkül a Kiadások-ból való törlés nyers 409-cel elhasalt ("még hivatkoznak rá
más rekordok"), és a felhasználónak semmilyen útja nem volt egy tévesen
felvezetett kifizetés visszavonására: a TIG-et sem lehetett törölni (mert ki
volt fizetve), a kiadást sem (mert a TIG hivatkozott rá).

A feloldás iránya SZÁNDÉKOSAN az, hogy a kiadás törlése a kifizetettséget is
visszavonja: a "ki van fizetve" állítás bizonyítéka éppen az a Kiadás sor volt.
Ha az nincs többé, a papír állapota sem maradhat "kifizetve" - különben egy
olyan TIG állna a rendszerben, amiről senki nem tudja megmondani, mikor és
miből fizettük ki. A kapcsolódó rekordok maguk MEGMARADNAK (csak a hivatkozás
és a kifizetettség szűnik meg), tehát a TIG, a számlái és a havi tétel a
helyükön vannak - csak újra teendővé válnak.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.employee_monthly_item import EmployeeMonthlyItem
from app.models.finance import Expense, KpForgalom
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.performance_certificate import PerformanceCertificate


@dataclass
class Bontas:
    """Mi történt a törléskor - a hívó ebből tud emberi üzenetet adni."""

    #: Kiknek a papírja került vissza "nincs kifizetve" állapotba.
    kifizetetlenne_valt: list[str] = field(default_factory=list)
    #: Hány egyéb rekordról (havi tétel, KP-forgalom) oldottuk le a hivatkozást.
    lekapcsolt_egyeb: int = 0


def _nev(cert: PerformanceCertificate | InternalPerformanceCertificate) -> str:
    ceg = getattr(cert, "ceg_neve", None)
    if ceg:
        return str(ceg)
    if cert.employee is not None:
        return cert.employee.full_name
    return f"#{cert.id}"


def bontsd_le_a_kapcsolatokat(expense: Expense, db: Session) -> Bontas:
    """A kiadásra mutató hivatkozások leoldása, a kifizetettség visszavonásával.

    Kizárólag a hivatkozó mezőket nyúlja - a rekordokat nem törli."""
    eredmeny = Bontas()

    for modell in (PerformanceCertificate, InternalPerformanceCertificate):
        for cert in db.query(modell).filter(modell.expense_id == expense.id).all():
            cert.expense_id = None
            cert.szamla_kifizetve = False
            eredmeny.kifizetetlenne_valt.append(_nev(cert))

    for tetel in db.query(EmployeeMonthlyItem).filter(EmployeeMonthlyItem.expense_id == expense.id).all():
        tetel.expense_id = None
        eredmeny.lekapcsolt_egyeb += 1

    # A KP-forgalom a készpénzmozgás naplója: a hozzá tartozó kiadás törlésekor
    # a mozgás maga megtörtént, csak már nem tudjuk, melyik kiadáshoz kötődött.
    for forgalom in db.query(KpForgalom).filter(KpForgalom.expense_id == expense.id).all():
        forgalom.expense_id = None
        eredmeny.lekapcsolt_egyeb += 1

    db.flush()
    return eredmeny
