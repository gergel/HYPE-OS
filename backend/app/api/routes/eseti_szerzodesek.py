"""Az összes alvállalkozói ESETI megbízási szerződés egy listában.

A Keretszerződések fül az ÁLLÓ keretszerződéseket mutatja (a Notion
"Alvállakozó keretszerződés (külsős)" táblájából). Minden más alvállalkozói
szerződés eseti megbízási szerződés - és eddig csak szétszórva, projektenként
(Utókövetés) vagy emberenként (a munkatárs adatlapján) lehetett rájuk látni.
Ez a végpont egyben adja őket: melyik EMBERHEZ és melyik PROJEKTHEZ tartozik
mindegyik, mennyiről szól, és hol a papír.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.contract import Contract, ContractType, megkotott_keretszerzodes
from app.models.employee import Employee, EmployeeType
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.services import szamlazo, tig_fedettseg

PAGE = "/penzugyek"

router = APIRouter(prefix="/eseti-szerzodesek", tags=["eseti-szerzodesek"])


class EsetiSzerzodes(BaseModel):
    id: int

    employee_id: int | None = None
    employee_nev: str | None = None
    employee_tipus: str | None = None

    #: Cég nevére szóló szerződésnél a számlázó vállalkozás (lásd
    #: services/szamlazo.py) - ilyenkor employee_id üres.
    vallalkozas_id: int | None = None
    vallalkozas_nev: str | None = None
    #: Kiknek a munkáját fedi ez az egy szerződés a projekten. Egynél több
    #: akkor, ha valaki más(ok) nevében is számláz.
    lefedettek: list[str] = []

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
            selectinload(Contract.vallalkozas),
            selectinload(Contract.project).selectinload(Project.project_code),
            selectinload(Contract.project).selectinload(Project.crew),
        )
        .filter(Contract.tipus == ContractType.ALVALLALKOZOI)
        .all()
    )
    # A "kit fed le" a projekt-beosztásból jön (lásd services/szamlazo.py),
    # nem a szerződésen tárolt adatból: a beosztás bármikor átállítható, és a
    # lista mindig a mostani állapotot mutassa.
    felulirasok = szamlazo.load_felulirasok(db, {c.project_id for c in szerzodesek if c.project_id})

    sorok: list[EsetiSzerzodes] = []
    for c in szerzodesek:
        if megkotott_keretszerzodes(c):
            continue
        netto = float(c.netto_osszeg) if c.netto_osszeg is not None else None
        projekt = c.project
        kulcs = f"v{c.vallalkozas_id}" if c.vallalkozas_id else (f"e{c.employee_id}" if c.employee_id else None)
        lefedettek: list[str] = []
        if projekt is not None and kulcs is not None:
            lefedettek = [
                e.full_name
                for e in projekt.crew
                if e.tipus != EmployeeType.BELSOS
                and szamlazo.szamlazo_fele(projekt, e, felulirasok).kulcs == kulcs
            ]
        sorok.append(
            EsetiSzerzodes(
                id=c.id,
                employee_id=c.employee_id,
                employee_nev=c.employee.full_name if c.employee else None,
                employee_tipus=c.employee.tipus.value if c.employee and c.employee.tipus else None,
                vallalkozas_id=c.vallalkozas_id,
                vallalkozas_nev=c.vallalkozas.nev if c.vallalkozas else None,
                lefedettek=lefedettek,
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


@router.delete("/{contract_id}", status_code=204)
def delete_eseti_szerzodes(
    contract_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Egy eseti megbízási szerződés teljes törlése.

    Ha a szerződés PROJEKTHEZ van kötve, a munkatárs ezután újra "hiányzik"
    azon a projekten, és készíthető neki új szerződés - ugyanaz, mint az
    Utókövetés oldali törlés (lásd routes/subcontractor_contracts.py
    delete_contract). Ha már készült hozzá TIG azon a projekten, előbb azt
    kell törölni: a TIG a szerződés lezárása UTÁN következő lépés, és a
    szerződés törlésével a projekt visszalép a szerződés-fázisba - a fázisok
    ne csúszhassanak egymásba.

    Keretszerződést itt nem lehet törölni: annak külön oldala (és külön
    jelentése) van."""
    szerzodes = db.get(Contract, contract_id)
    if szerzodes is None or szerzodes.tipus != ContractType.ALVALLALKOZOI:
        raise HTTPException(status_code=404, detail="Az eseti szerződés nem található.")
    if megkotott_keretszerzodes(szerzodes):
        raise HTTPException(
            status_code=400,
            detail="Ez álló keretszerződés, nem eseti - a Keretszerződések oldalon törölhető.",
        )
    if szerzodes.project_id is not None:
        # A TIG-et a TÉTELEIN keresztül keressük: egy fél TIG-je indulhatott
        # másik projektről is (több forgatás egy számlán), attól még ezt a
        # projektet igazolja.
        van_tig = (
            db.query(PerformanceCertificate.id)
            .filter(tig_fedettseg.fedi_a_projektet(szerzodes.project_id))
            .filter(
                PerformanceCertificate.vallalkozas_id == szerzodes.vallalkozas_id
                if szerzodes.vallalkozas_id is not None
                else (
                    (PerformanceCertificate.employee_id == szerzodes.employee_id)
                    & PerformanceCertificate.vallalkozas_id.is_(None)
                )
            )
            .first()
        )
        if van_tig is not None:
            raise HTTPException(
                status_code=400,
                detail="Ehhez az emberhez már készült TIG ezen a projekten - előbb a TIG-et kell törölni.",
            )
    db.delete(szerzodes)
    db.commit()
