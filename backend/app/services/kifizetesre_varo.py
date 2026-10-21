"""KIFIZETÉSRE VÁRÓ kiadások (a felhasználó kérése): amit már felvezettünk
(pl. jött róla számla), de még nem fizettünk ki.

Egy kiadás akkor vár kifizetésre, ha
  - nincs kifizetve (`kesz`) és nincs fizetési dátuma - a fizetés dátumát a
    "Fizetés" gomb írja rá, attól kerül a Kiadások közé és az egyenlegekbe;
  - nem TIG-ből / havi tételből keletkezett (azt a saját papírja fizeti ki,
    és a TIG már az Utalásra váró listán van);
  - és nem a régi Notion-importból maradt dátum nélküli sor - azok a régi
    rendszerben könyvelt, megtörtént fizetések voltak (lásd
    routes/finance._utalasra_varo_tetelek), hacsak nincs fizetési
    határidejük, mert akkor kifejezetten fizetendőként rögzítették őket.

A kimutatások (ytd kiadás, havi trend, számla- és KP-egyenleg) ettől
függetlenül is csak a kifizetett kiadást számolják (lásd
routes/finance._EXPENSE_COUNTS_TOWARD_TOTALS és services/kassza.py)."""

from __future__ import annotations

from sqlalchemy import or_, select, union
from sqlalchemy.orm import Session, selectinload

from app.models.employee_monthly_item import EmployeeMonthlyItem
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.notion_import import NotionImportMap
from app.models.performance_certificate import PerformanceCertificate


def _papirbol_keletkezett_idk():
    return union(
        *(
            select(m.expense_id).where(m.expense_id.is_not(None))
            for m in (PerformanceCertificate, InternalPerformanceCertificate, EmployeeMonthlyItem)
        )
    )


def szuro():
    """SQL-feltétel a kifizetésre váró kiadásokra (lásd a modul leírását)."""
    notionos = select(NotionImportMap.entity_id).where(NotionImportMap.entity_type == "Expense")
    return (
        Expense.kesz.is_not(True)
        & Expense.fizetes_datuma.is_(None)
        & Expense.id.not_in(_papirbol_keletkezett_idk())
        & or_(Expense.fizetes_hatarideje.is_not(None), Expense.id.not_in(notionos))
    )


def kiadasok(db: Session, *, csak_hataridos: bool = False) -> list[Expense]:
    """A kifizetésre váró kiadások, a legkorábbi határidő elöl (határidő
    nélküliek a végén). `csak_hataridos`: csak a fizetési határidővel
    rögzítettek - az Utalásra váró lista ezeket hozza."""
    feltetel = szuro()
    if csak_hataridos:
        feltetel = feltetel & Expense.fizetes_hatarideje.is_not(None)
    sorok = db.scalars(
        select(Expense)
        .where(feltetel)
        .options(selectinload(Expense.auto), selectinload(Expense.project_code))
    ).all()
    return sorted(sorok, key=lambda e: (e.fizetes_hatarideje is None, e.fizetes_hatarideje, -e.id))
