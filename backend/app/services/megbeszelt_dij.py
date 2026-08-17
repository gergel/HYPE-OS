"""A stábtaggal lebeszélt napidíj - és ahogy a papírokra kerül.

A díj a (projekt, ember) páron él (lásd models/project_szamlazo.py): a diszpó
írásakor, a stábtag felvételekor rögzítik, mennyiért vállalja azt a napot.

Innen két helyre kell eljutnia, mert a papírt hetekkel később, más ember
készíti, mint aki a díjat megbeszélte:

- az ESETI SZERZŐDÉS piszkozatára,
- és a TIG piszkozatára - akkor is, ha eseti szerződés nincs, mert a felet
  keretszerződés fedi.

Egy papír TÖBB ember munkájáról is szólhat (egy fél számláz többekért), ezért
a fejösszeg a tagok díjainak ÖSSZEGE, a tételekre pedig fejenként az övé kerül.
Ha senkinél nincs megadva díj, a piszkozat összeg nélkül nyílik - előtöltés
helyett üres mező, mert egy kitalált szám rosszabb, mint a hiánya.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_szamlazo import ProjectSzamlazo


def dijak_a_projekten(db: Session, project_id: int) -> dict[int, float]:
    """{employee_id: megbeszélt nettó díj} - csak akiknél meg van adva."""
    sorok = db.execute(
        select(ProjectSzamlazo.employee_id, ProjectSzamlazo.megbeszelt_dij).where(
            ProjectSzamlazo.project_id == project_id,
            ProjectSzamlazo.megbeszelt_dij.is_not(None),
        )
    ).all()
    return {employee_id: float(dij) for employee_id, dij in sorok}


def csoport_osszege(dijak: dict[int, float], tag_idk: list[int]) -> float | None:
    """A papír fejösszege: a rá tartozó emberek díjainak összege.

    None, ha egyiküknél sincs megadva díj - ilyenkor nincs mit előtölteni.
    Ha csak NÉHÁNYUKNÁL van, azokat összegezzük: az is közelebb van a
    valósághoz, mint az üres mező, és a készítő úgyis látja a tételeket."""
    ismert = [dijak[tag_id] for tag_id in tag_idk if tag_id in dijak]
    if not ismert:
        return None
    return sum(ismert)
