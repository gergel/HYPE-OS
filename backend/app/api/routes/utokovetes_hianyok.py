"""Utókövetés - hiányzó alvállalkozói dokumentumok és az emlékeztető-mátrix.

KÜLÖN router, de ugyanazon a `/utokovetes` előtagon, mint az áttekintő
(routes/utokovetes_admin.py) - és ELŐTTE kell regisztrálni, különben a
`/utokovetes/{project_id}` útvonal nyelné el a `/utokovetes/hianyok` kérést.
A logika: services/utokovetes_hianyok.py."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.employee import Employee, SystemRole
from app.services import utokovetes_hianyok

router = APIRouter(prefix="/utokovetes", tags=["utokovetes-hianyok"])

PAGE = "/utokovetes"
_MINDEN_SZEREPKOR = tuple(SystemRole)


@router.get("/hianyok")
def hianyok(
    napok: int | None = Query(120, ge=1, le=3650, description="Hány napra visszamenőleg (a forgatás vége szerint)"),
    csak_hianyos: bool = True,
    project_id: int | None = None,
    ma: date | None = Query(None, description="Tesztelési/visszamenőleges nézethez - alapból a mai nap"),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A lezajlott forgatások számlázó felei × (szerződés, TIG, számla):
    élő dokumentum-állapot, a kiküldött emlékeztetők száma és az utolsó
    értesítés ideje. Alapból csak a hiányos sorok. Csak olvas."""
    return utokovetes_hianyok.matrix(db, ma=ma, napok=napok, csak_hianyos=csak_hianyos, project_id=project_id)


class EmlekeztetoIn(BaseModel):
    project_id: int
    szamlazo_kulcs: str = Field(..., pattern=r"^[ev]\d+$")
    dokumentum_tipus: Literal["szerzodes", "tig", "szamla"]
    csatorna: Literal["email", "telefon", "szemelyes", "egyeb"] = "email"
    megjegyzes: str | None = Field(None, max_length=2000)


@router.post("/hianyok/emlekezteto")
def emlekezteto(
    payload: EmlekeztetoIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy KIKÜLDÖTT emlékeztető rögzítése (darabszám +1, utolsó értesítés
    ideje, állapot az értesítéskor). Levelet NEM küld - csak a tényt jegyzi,
    és az audit-naplóba írja."""
    try:
        rekord = utokovetes_hianyok.emlekezteto_rogzitese(
            db,
            project_id=payload.project_id,
            szamlazo_kulcs=payload.szamlazo_kulcs,
            dokumentum_tipus=payload.dokumentum_tipus,
            csatorna=payload.csatorna,
            megjegyzes=payload.megjegyzes,
            user=current_user,
        )
    except utokovetes_hianyok.HianyHiba as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {
        "id": rekord.id,
        "project_id": rekord.project_id,
        "szamlazo_kulcs": rekord.szamlazo_kulcs,
        "dokumentum_tipus": rekord.dokumentum_tipus,
        "emlekezteto_db": rekord.emlekezteto_db,
        "utolso_ertesites_at": rekord.utolso_ertesites_at.isoformat() if rekord.utolso_ertesites_at else None,
        "utolso_ertesites_csatorna": rekord.utolso_ertesites_csatorna,
        "allapot_ertesiteskor": rekord.allapot_ertesiteskor,
    }
