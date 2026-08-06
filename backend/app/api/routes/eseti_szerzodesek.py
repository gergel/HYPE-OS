"""Az összes alvállalkozói ESETI megbízási szerződés egy listában.

A Keretszerződések fül az ÁLLÓ keretszerződéseket mutatja (a Notion
"Alvállakozó keretszerződés (külsős)" táblájából). Minden más alvállalkozói
szerződés eseti megbízási szerződés - és eddig csak szétszórva, projektenként
(Utókövetés) vagy emberenként (a munkatárs adatlapján) lehetett rájuk látni.
Ez a végpont egyben adja őket: melyik EMBERHEZ és melyik PROJEKTHEZ tartozik
mindegyik, mennyiről szól, és hol a papír.
"""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.contract import Contract, ContractType, megkotott_keretszerzodes
from app.models.employee import Employee
from app.models.project import Project

PAGE = "/penzugyek"

router = APIRouter(prefix="/eseti-szerzodesek", tags=["eseti-szerzodesek"])


class EsetiSzerzodes(BaseModel):
    id: int

    employee_id: int | None = None
    employee_nev: str | None = None
    employee_tipus: str | None = None

    #: Projekt nélkül is lehet eseti szerződés: a munkatárs Notion-lapjáról
    #: átvett, cégadat + aláírt PDF sorok nincsenek projekthez kötve.
    project_id: int | None = None
    project_nev: str | None = None
    projektkod: str | None = None
    forgatas_datuma: date | None = None

    ceg_neve: str | None = None
    megbizas_targya: str | None = None
    szerzodes_allapota: str | None = None
    netto_osszeg: float | None = None
    brutto_osszeg: float | None = None
    plusz_afa: bool | None = None
    teljesites_szoveg: str | None = None
    keltezes: date | None = None
    alairva: bool = False
    szerzodes_file_url: str | None = None


def _teljesites(c: Contract) -> str | None:
    """Ugyanaz a szöveg, ami a szerződésre kerül (lásd
    routes/subcontractor_contracts.py _teljesites_szovege): elsősorban a szabad
    szöveges mező, és csak a régi, dátumpáros bejegyzéseknél a két dátumból."""
    szoveg = (c.teljesites_szoveg or "").strip()
    if szoveg:
        return szoveg
    if c.teljesites_vege and c.teljesites_vege != c.teljesites_kezdete:
        kezdet = c.teljesites_kezdete.strftime("%Y.%m.%d.") if c.teljesites_kezdete else ""
        return f"{kezdet} - {c.teljesites_vege.strftime('%Y.%m.%d.')}"
    if c.teljesites_kezdete:
        return c.teljesites_kezdete.strftime("%Y.%m.%d.")
    return None


@router.get("", response_model=list[EsetiSzerzodes])
def list_eseti_szerzodesek(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    """Minden alvállalkozói eseti megbízási szerződés, emberrel és projekttel.

    A legfrissebb elöl: a forgatás dátuma szerint, dátum nélkül a keltezés,
    végül az azonosító dönt - így a most készült szerződések vannak felül."""
    szerzodesek = (
        db.query(Contract)
        .options(
            selectinload(Contract.employee),
            selectinload(Contract.project).selectinload(Project.project_code),
        )
        .filter(Contract.tipus == ContractType.ALVALLALKOZOI)
        .all()
    )

    sorok: list[EsetiSzerzodes] = []
    for c in szerzodesek:
        if megkotott_keretszerzodes(c):
            continue
        netto = float(c.netto_osszeg) if c.netto_osszeg is not None else None
        projekt = c.project
        sorok.append(
            EsetiSzerzodes(
                id=c.id,
                employee_id=c.employee_id,
                employee_nev=c.employee.full_name if c.employee else None,
                employee_tipus=c.employee.tipus.value if c.employee and c.employee.tipus else None,
                project_id=c.project_id,
                project_nev=projekt.nev if projekt else None,
                projektkod=projekt.project_code.projektkod if projekt and projekt.project_code else None,
                forgatas_datuma=projekt.forgatas_datuma if projekt else None,
                ceg_neve=c.ceg_neve,
                megbizas_targya=c.megbizas_targya,
                szerzodes_allapota=c.szerzodes_allapota,
                netto_osszeg=netto,
                brutto_osszeg=round(netto * 1.27, 2) if (netto is not None and c.plusz_afa) else netto,
                plusz_afa=c.plusz_afa,
                teljesites_szoveg=_teljesites(c),
                keltezes=c.keltezes,
                alairva=bool(c.alairva),
                szerzodes_file_url=c.szerzodes_file_url,
            )
        )

    sorok.sort(key=lambda s: (s.forgatas_datuma or s.keltezes or date.min, s.id), reverse=True)
    return sorok
