from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.project_code import ProjectCode
from app.schemas.finance import (
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    KpForgalomCreate,
    KpForgalomRead,
    KpForgalomUpdate,
    RevenueCreate,
    RevenueRead,
    RevenueUpdate,
)

expenses_router = build_crud_router(
    model=Expense,
    create_schema=ExpenseCreate,
    update_schema=ExpenseUpdate,
    read_schema=ExpenseRead,
    prefix="/expenses",
    tags=["finance"],
    page="/penzugyek",
)

revenues_router = build_crud_router(
    model=Revenue,
    create_schema=RevenueCreate,
    update_schema=RevenueUpdate,
    read_schema=RevenueRead,
    prefix="/revenues",
    tags=["finance"],
    page="/penzugyek",
)

kp_forgalom_router = build_crud_router(
    model=KpForgalom,
    create_schema=KpForgalomCreate,
    update_schema=KpForgalomUpdate,
    read_schema=KpForgalomRead,
    prefix="/kp-forgalom",
    tags=["finance"],
    page="/penzugyek",
)

summary_router = APIRouter(prefix="/finance", tags=["finance"])


class MonthlyFinance(BaseModel):
    month: str
    bevetel: float
    kiadas: float


class OutstandingProject(BaseModel):
    project_code_id: int
    projektkod: str
    ugyfel_nev: str | None
    kintlevo_osszeg: float
    legkorabbi_hatarido: date | None
    lejart: bool


class PaymentMethodBreakdown(BaseModel):
    kifizetes_modja: str | None
    osszeg: float


class FinanceSummary(BaseModel):
    ytd_bevetel: float
    ytd_kiadas: float
    ytd_profit: float
    osszes_kintlevoseg: float
    kintlevo_projektek_szama: int
    havi_trend: list[MonthlyFinance]
    kintlevo_projektek: list[OutstandingProject]
    ytd_kiadas_fizetesi_mod_szerint: list[PaymentMethodBreakdown]


# Egy kiadás csak akkor számít bele a Pénzügy összesítőkbe (YTD kiadás, havi
# trend, fizetési mód szerinti bontás), ha a "Hozzá adás a kiadásokhoz"
# checkbox nincs kifejezetten kikapcsolva - a régi Notion-import forrásai
# (sima "Kiadások" / "Belsős extra kiadások" táblák) nem is ismerték ezt a
# mezőt, ott NULL-ként importálódott, ezért a NULL-t "számítson bele"-ként
# kezeljük (nem "nincs bepipálva"-ként), hogy a checkbox bevezetése ne
# tüntessen el némán történeti kiadásokat az összesítőkből - csak a
# kifejezetten (a "Projekt kiadások" felvitelnél) kipipálatlanul hagyott
# sorok esnek ki. A projektkód-szintű Expense.brutto összeg (ProjectCode.
# osszes_koltseg) ettől függetlenül MINDIG az adott projekt teljes,
# valós költségét mutatja - ez a gate csak a globális Pénzügy nézetet szűri.
_EXPENSE_COUNTS_TOWARD_TOTALS = Expense.hozzaadas_a_kiadasokhoz.is_not(False)


def _last_n_months(today: date, n: int) -> list[tuple[int, int]]:
    """[(év, hónap), ...] a mai hónapig bezárólag, régitől az újig rendezve -
    ugyanaz a helper, mint a dashboard.py revenue_trend-jénél."""
    months = []
    year, month = today.year, today.month
    for _ in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


@summary_router.get("/summary", response_model=FinanceSummary)
def finance_summary(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A Pénzügyek oldal nagy összesítője: éves (YTD) bevétel/kiadás/profit,
    az utolsó 12 hónap bevétel+kiadás trendje, és a kintlévőségek (kifizetetlen
    bevétel-sorok, azaz Revenue.fizetes_datuma IS NULL) project code-onként
    összesítve, a legnagyobb összeggel elöl."""
    today = date.today()
    year_start = date(today.year, 1, 1)

    ytd_bevetel = (
        db.scalar(
            select(func.coalesce(func.sum(Revenue.brutto), 0)).where(
                Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= year_start
            )
        )
        or 0
    )
    ytd_kiadas = (
        db.scalar(
            select(func.coalesce(func.sum(Expense.brutto), 0)).where(
                Expense.fizetes_datuma.is_not(None),
                Expense.fizetes_datuma >= year_start,
                _EXPENSE_COUNTS_TOWARD_TOTALS,
            )
        )
        or 0
    )

    months = _last_n_months(today, 12)
    min_year, min_month = months[0]
    min_date = date(min_year, min_month, 1)

    revenue_by_month: dict[tuple[int, int], float] = {}
    for row in db.execute(
        select(
            extract("year", Revenue.fizetes_datuma).label("y"),
            extract("month", Revenue.fizetes_datuma).label("m"),
            func.coalesce(func.sum(Revenue.brutto), 0).label("total"),
        )
        .where(Revenue.fizetes_datuma.is_not(None), Revenue.fizetes_datuma >= min_date)
        .group_by("y", "m")
    ).all():
        revenue_by_month[(int(row.y), int(row.m))] = float(row.total)

    expense_by_month: dict[tuple[int, int], float] = {}
    for row in db.execute(
        select(
            extract("year", Expense.fizetes_datuma).label("y"),
            extract("month", Expense.fizetes_datuma).label("m"),
            func.coalesce(func.sum(Expense.brutto), 0).label("total"),
        )
        .where(Expense.fizetes_datuma.is_not(None), Expense.fizetes_datuma >= min_date, _EXPENSE_COUNTS_TOWARD_TOTALS)
        .group_by("y", "m")
    ).all():
        expense_by_month[(int(row.y), int(row.m))] = float(row.total)

    ytd_kiadas_fizetesi_mod_szerint = [
        PaymentMethodBreakdown(kifizetes_modja=row.kifizetes_modja, osszeg=float(row.total))
        for row in db.execute(
            select(Expense.kifizetes_modja, func.coalesce(func.sum(Expense.brutto), 0).label("total"))
            .where(Expense.fizetes_datuma.is_not(None), Expense.fizetes_datuma >= year_start, _EXPENSE_COUNTS_TOWARD_TOTALS)
            .group_by(Expense.kifizetes_modja)
            .order_by(func.sum(Expense.brutto).desc())
        ).all()
    ]

    havi_trend = [
        MonthlyFinance(
            month=f"{y:04d}-{m:02d}",
            bevetel=revenue_by_month.get((y, m), 0.0),
            kiadas=expense_by_month.get((y, m), 0.0),
        )
        for y, m in months
    ]

    unpaid = db.scalars(
        select(Revenue)
        .where(Revenue.fizetes_datuma.is_(None))
        .options(selectinload(Revenue.project_code).selectinload(ProjectCode.client))
    ).all()

    by_project: dict[int, list[Revenue]] = {}
    for r in unpaid:
        by_project.setdefault(r.project_code_id, []).append(r)

    kintlevo_projektek: list[OutstandingProject] = []
    for pc_id, rows in by_project.items():
        pc = rows[0].project_code
        osszeg = sum(r.brutto or 0 for r in rows)
        hataridok = [r.fizetes_hatarideje for r in rows if r.fizetes_hatarideje]
        legkorabbi = min(hataridok) if hataridok else None
        kintlevo_projektek.append(
            OutstandingProject(
                project_code_id=pc_id,
                projektkod=pc.projektkod if pc else f"#{pc_id}",
                ugyfel_nev=pc.client.nev if pc and pc.client else None,
                kintlevo_osszeg=osszeg,
                legkorabbi_hatarido=legkorabbi,
                lejart=bool(legkorabbi and legkorabbi < today),
            )
        )
    kintlevo_projektek.sort(key=lambda p: p.kintlevo_osszeg, reverse=True)
    osszes_kintlevoseg = sum(p.kintlevo_osszeg for p in kintlevo_projektek)

    return FinanceSummary(
        ytd_bevetel=float(ytd_bevetel),
        ytd_kiadas=float(ytd_kiadas),
        ytd_profit=float(ytd_bevetel) - float(ytd_kiadas),
        osszes_kintlevoseg=osszes_kintlevoseg,
        kintlevo_projektek_szama=len(kintlevo_projektek),
        havi_trend=havi_trend,
        kintlevo_projektek=kintlevo_projektek[:15],
        ytd_kiadas_fizetesi_mod_szerint=ytd_kiadas_fizetesi_mod_szerint,
    )
