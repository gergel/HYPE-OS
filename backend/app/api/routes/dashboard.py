"""Dashboard modul - a mockup összegző kártyáinak valós lekérdezései."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.finance import Revenue
from app.models.project import Project
from app.models.project_code import ProjectCode

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    mai_forgatasok: int
    aktiv_project_codeok: int
    equipment_utkozesek: int
    havi_bevetel: float


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):
    today = date.today()

    mai_forgatasok = (
        db.scalar(select(func.count()).select_from(Project).where(Project.forgatas_datuma == today)) or 0
    )
    aktiv_project_codeok = (
        db.scalar(
            select(func.count())
            .select_from(ProjectCode)
            .where(or_(ProjectCode.esemeny_allapota.is_(None), ProjectCode.esemeny_allapota != "lezarva"))
        )
        or 0
    )
    havi_bevetel = (
        db.scalar(
            select(func.coalesce(func.sum(Revenue.brutto), 0)).where(
                extract("year", Revenue.fizetes_datuma) == today.year,
                extract("month", Revenue.fizetes_datuma) == today.month,
            )
        )
        or 0
    )

    return DashboardSummary(
        mai_forgatasok=mai_forgatasok,
        aktiv_project_codeok=aktiv_project_codeok,
        # az Equipment modul már felvételkor (POST /assignments) elutasítja az ütköző
        # foglalást (409), tehát a DB-ben soha nincs ütköző pár - ez a kártya ezt jelzi
        equipment_utkozesek=0,
        havi_bevetel=float(havi_bevetel),
    )
