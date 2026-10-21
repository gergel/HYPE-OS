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

from app.models.contract import Contract
from app.models.employee_monthly_item import EmployeeMonthlyItem
from app.models.finance import Expense, KpForgalom
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.performance_certificate import PerformanceCertificate
from app.services import document_storage


@dataclass
class Bontas:
    """Mi történt a törléskor - a hívó ebből tud emberi üzenetet adni."""

    #: Kiknek a papírja került vissza "nincs kifizetve" állapotba.
    kifizetetlenne_valt: list[str] = field(default_factory=list)
    #: Hány egyéb rekordról (havi tétel, KP-forgalom) oldottuk le a hivatkozást.
    lekapcsolt_egyeb: int = 0


def _nev(cert: PerformanceCertificate | InternalPerformanceCertificate | Contract) -> str:
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


def torold_alvallalkozoi_papirokat_ha_utolso(expense: Expense, db: Session) -> list[str]:
    """Ha ez volt az UTOLSÓ olyan kiadás, ami ezt az embert erre a FORGATÁS
    NÉLKÜLI projektkódra alvállalkozóként jelölte (lásd
    models/project_code.py ProjectCode.alvallalkozo_stab_forgatas_nelkul),
    a hozzá tartozó eseti szerződést és TIG-et is törli.

    Ez a fenti `bontsd_le_a_kapcsolatokat`-tal ELLENTÉTES irányú kapcsolat: az
    a kiadást VÉDI a rá mutató papírtól (leoldja a hivatkozást, a papír
    megmarad), ez viszont a papírt köti a kiadáshoz - ha a kiadás (ami miatt
    a szerződés/TIG egyáltalán kellett) megszűnik, a papír önmagában
    értelmetlen teendővé válna: a projektkód "alvállalkozói stábjából" (lásd
    ProjectCode.alvallalkozo_stab_forgatas_nelkul) eltűnik az illető, tehát a
    felületen se megtalálni, se lezárni nem lehetne többé a papírját.

    Ha az embernek MÁS kiadása is van még ugyanezen a projektkódon, a papírt
    NEM bántjuk: neki továbbra is kellhet szerződés/TIG, csak épp egy másik
    kiadás miatt - a deduplikált stáblista (lásd
    ProjectCode.alvallalkozo_stab_forgatas_nelkul) ettől még ugyanúgy
    tartalmazza. Ebbe a "másik kiadás"-ba viszont NEM számít bele az a
    kiadás-sor, amit a TIG saját kifizetése hozott létre (lásd
    performance_certificates.py mark_szamla_kifizetve_projektkodon,
    PerformanceCertificate.expense_id) - az ilyen sor önmagában NEM önálló ok
    arra, hogy az illetőnek papírt kelljen tartani, hanem épp annak a
    papírnak a KÖVETKEZMÉNYE, amit itt törlünk; ha mégis "másik kiadásnak"
    számítana, egy már kifizetett TIG-nél ez a törlés soha nem futna le.

    A TIG-hez feltöltött számlák a tárhelyről is törlődnek (a DB-sorukat az
    ORM cascade viszi) - ugyanaz a minta, mint delete_certificate(_projektkodon)
    végpontoknál. A szerződés/TIG SAJÁT dokumentuma (generált vagy feltöltött
    fájl) a tárhelyen marad - ugyanúgy, ahogy azok a végpontok is hagyják.

    Visszaadja, kinek a papírja került törlésre (emberi üzenethez)."""
    if expense.employee_id is None or expense.alvallalkozo_project_id is not None or expense.project_code_id is None:
        return []
    kifizetesi_expense_idk = {
        eid
        for (eid,) in db.query(PerformanceCertificate.expense_id).filter(
            PerformanceCertificate.expense_id.is_not(None)
        )
    }
    masik_kiadas_lekerdezes = db.query(Expense.id).filter(
        Expense.project_code_id == expense.project_code_id,
        Expense.employee_id == expense.employee_id,
        Expense.alvallalkozo_project_id.is_(None),
        Expense.id != expense.id,
    )
    if kifizetesi_expense_idk:
        masik_kiadas_lekerdezes = masik_kiadas_lekerdezes.filter(Expense.id.notin_(kifizetesi_expense_idk))
    if masik_kiadas_lekerdezes.first() is not None:
        return []

    torolt: list[str] = []

    tigek = (
        db.query(PerformanceCertificate)
        .filter(
            PerformanceCertificate.project_code_id == expense.project_code_id,
            PerformanceCertificate.employee_id == expense.employee_id,
        )
        .all()
    )
    for tig in tigek:
        for invoice in tig.invoices:
            document_storage.delete_object(invoice.storage_key)
        torolt.append(_nev(tig))
        db.delete(tig)

    szerzodesek = (
        db.query(Contract)
        .filter(
            Contract.project_code_id == expense.project_code_id,
            Contract.employee_id == expense.employee_id,
        )
        .all()
    )
    for szerzodes in szerzodesek:
        nev = _nev(szerzodes)
        if nev not in torolt:
            torolt.append(nev)
        db.delete(szerzodes)

    db.flush()
    return torolt
