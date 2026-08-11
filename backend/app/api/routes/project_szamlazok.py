"""Projektenként: kinek a munkáját ki számlázza.

Ez a felület mögötti végpont a projekt stáblistáján lévő "Ki számláz" oszlophoz
(lásd models/project_szamlazo.py). Alapból mindenki magának számláz - ilyenkor
nincs is sor a táblában.

Két tipikus beállítás:

- "Balla Berci munkáját Ladányi Máté számlázza" -> egy szerződés és egy TIG
  megy ki, Ladányi nevére, mindkettőjük munkájáról. Berci attól még STÁBTAG
  marad: kap diszpót, rajta van a projekten.
- "Ezt az embert a XY Kft. küldte" -> a cég számláz. Ha a cégnek van élő
  keretszerződése, eseti szerződés sem kell."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee, EmployeeType
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.vallalkozas import Vallalkozas, VallalkozasTag
from app.services import belsos_idoszak, papir_fedettseg, szamlazo

router = APIRouter(prefix="/projekt-szamlazok", tags=["projekt-szamlazok"])

PAGE = "/projektek"


class JavaslatInfo(BaseModel):
    """Egy felajánlható számlázó fél."""

    szamlazo: str
    nev: str
    #: Miért ajánljuk: "sajat" | "vallalkozas-tagsag" | "stabtars"
    forras: str


class SzamlazoSor(BaseModel):
    employee_id: int
    full_name: str
    tipus: str | None = None
    #: A jelenlegi számlázó fél kulcsa - saját magánál "e{employee_id}".
    szamlazo: str
    szamlazo_nev: str
    #: Igaz, ha nem ő maga számláz (ilyenkor van felülírás-sor).
    felulirva: bool
    megjegyzes: str | None = None
    javaslatok: list[JavaslatInfo] = []


class ValaszthatoFel(BaseModel):
    """Egy ember, aki EZEN a projekten számlázó fél lehet."""

    szamlazo: str
    nev: str


class ProjektSzamlazoNezet(BaseModel):
    project_id: int
    project_nev: str | None = None
    sorok: list[SzamlazoSor]
    #: Kik választhatók számlázó félként ezen a projekten - a javaslatokon
    #: FELÜL, tehát olyanok is, akik nincsenek rajta a projekten. A listát a
    #: szerver állítja össze, mert a "belsős-e" kérdés IDŐSZAKOS, és csak itt
    #: van meg hozzá az adat (lásd _valaszthato_emberek).
    valaszthato_emberek: list[ValaszthatoFel] = []


class SzamlazoIn(BaseModel):
    #: "e12" / "v3", vagy None/üres: álljon vissza saját magára.
    szamlazo: str | None = None
    megjegyzes: str | None = None


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


def _lehet_szamlazo(employee: Employee, nap: date | None) -> bool:
    """Lehet-e ez az ember számlázó fél egy adott NAPON zajló projekten?

    A belsős munkatárs havi bérezésű, nála nincs projektenkénti számlázás -
    DE a belsős státusz időszakos: aki ma belsős, tavaly még külsősként
    dolgozhatott, és akkor simán ő számlázhatott más helyett. Ezért nem a mai
    típus dönt önmagában, hanem az, hogy az adott napon belsős volt-e."""
    if employee.tipus != EmployeeType.BELSOS:
        return True
    return belsos_idoszak.bizonyithatoan_nem_belsos(employee, nap)


def _valaszthato_emberek(db: Session, project: Project) -> list[ValaszthatoFel]:
    """Minden ember, aki ezen a projekten számlázó fél lehet.

    Szándékosan a szerver állítja össze: a felület nem tudhatja, ki mikor volt
    belsős (a belsős időszakok itt vannak), és a szabályt sem akarjuk két
    helyen karbantartani."""
    emberek = db.scalars(
        select(Employee).options(selectinload(Employee.belsos_idoszakok)).order_by(Employee.full_name)
    ).all()
    return [
        ValaszthatoFel(szamlazo=f"e{e.id}", nev=e.full_name)
        for e in emberek
        if _lehet_szamlazo(e, project.forgatas_datuma)
    ]


def _javaslatok(db: Session, project: Project, employee: Employee) -> list[JavaslatInfo]:
    """Kit érdemes felajánlani ennél az embernél?

    Sorrendben: saját maga (az alapeset), a cégei (ahol tag), végül a projekt
    többi nem belsős stábtagja - ez utóbbi az "egyikük számlázza a másikat"
    eset, ami a felhasználó szerint gyakori."""
    javaslatok = [JavaslatInfo(szamlazo=f"e{employee.id}", nev=employee.full_name, forras="sajat")]
    tagsagok = (
        db.query(VallalkozasTag)
        .options(selectinload(VallalkozasTag.vallalkozas))
        .filter(VallalkozasTag.employee_id == employee.id)
        .all()
    )
    for t in tagsagok:
        if t.vallalkozas is not None and t.vallalkozas.aktiv:
            javaslatok.append(
                JavaslatInfo(szamlazo=f"v{t.vallalkozas.id}", nev=t.vallalkozas.nev, forras="vallalkozas-tagsag")
            )
    for tars in project.crew:
        # A belsős stábtárs is lehet számlázó, ha a forgatás napján épp NEM
        # volt belsős (lásd _lehet_szamlazo).
        if tars.id == employee.id or not _lehet_szamlazo(tars, project.forgatas_datuma):
            continue
        javaslatok.append(JavaslatInfo(szamlazo=f"e{tars.id}", nev=tars.full_name, forras="stabtars"))
    return javaslatok


@router.get("/{project_id}", response_model=ProjektSzamlazoNezet)
def get_projekt_szamlazok(
    project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    """A projekt nem belsős stábtagjai, mindegyiknél a jelenlegi számlázó
    féllel és a választható lehetőségekkel."""
    project = _get_project_or_404(db, project_id)
    felulirasok = szamlazo.load_felulirasok(db, {project.id})
    sorok: list[SzamlazoSor] = []
    for e in project.crew:
        if e.tipus == EmployeeType.BELSOS:
            continue
        fel = szamlazo.szamlazo_fele(project, e, felulirasok)
        sor = felulirasok.get((project.id, e.id))
        sorok.append(
            SzamlazoSor(
                employee_id=e.id,
                full_name=e.full_name,
                tipus=e.tipus.value if e.tipus else None,
                szamlazo=fel.kulcs,
                szamlazo_nev=fel.nev,
                felulirva=fel.kulcs != f"e{e.id}",
                megjegyzes=sor.megjegyzes if sor else None,
                javaslatok=_javaslatok(db, project, e),
            )
        )
    return ProjektSzamlazoNezet(
        project_id=project.id,
        project_nev=project.nev,
        sorok=sorok,
        valaszthato_emberek=_valaszthato_emberek(db, project),
    )


def _van_papir(db: Session, project_id: int, employee_id: int) -> bool:
    """Készült-e már TIG erről a munkáról? Ha igen, a számlázó fél átállítása
    utólag hazuggá tenné a papírt - előbb a TIG-et kell rendezni."""
    return papir_fedettseg.van_papir_a_munkara(
        db, PerformanceCertificate, PerformanceCertificateTetel, project_id, employee_id
    )


@router.put("/{project_id}/{employee_id}", response_model=ProjektSzamlazoNezet)
def set_szamlazo(
    project_id: int,
    employee_id: int,
    payload: SzamlazoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A számlázó fél beállítása (vagy visszaállítása saját magára, üres
    értékkel)."""
    project = _get_project_or_404(db, project_id)
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található")
    if employee not in project.crew:
        raise HTTPException(status_code=400, detail="Ez a munkatárs nincs a projekt stábjában.")
    if employee.tipus == EmployeeType.BELSOS:
        raise HTTPException(
            status_code=400,
            detail="Belsős munkatárs havi bérezésű - nála nincs projektenkénti számlázó fél.",
        )
    if _van_papir(db, project.id, employee.id):
        raise HTTPException(
            status_code=400,
            detail="Erről a munkáról már készült TIG - előbb azt kell törölni, csak utána állítható át, ki számláz.",
        )

    sor = db.query(ProjectSzamlazo).filter_by(project_id=project.id, employee_id=employee.id).first()
    kulcs = (payload.szamlazo or "").strip()

    # Üres érték vagy önmaga: nincs mit felülírni, a sor törlődik.
    if not kulcs or kulcs == f"e{employee.id}":
        if sor is not None:
            db.delete(sor)
            db.commit()
        return get_projekt_szamlazok(project.id, db, _user)

    fel = szamlazo.feloldas(db, kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A választott számlázó fél nem található.")
    if fel.employee is not None and not _lehet_szamlazo(fel.employee, project.forgatas_datuma):
        raise HTTPException(
            status_code=400,
            detail="Belsős munkatárs nem lehet számlázó fél - a forgatás idején belsősként dolgozott.",
        )
    if fel.vallalkozas is not None and not fel.vallalkozas.aktiv:
        raise HTTPException(status_code=400, detail="Ez a vállalkozás inaktív.")
    # Láncot nem engedünk: ha A-t B számlázza, B-t nem számlázhatja C - a papír
    # ilyenkor nem tudná, kinek a nevére szóljon.
    if fel.employee is not None:
        tovabbi = db.query(ProjectSzamlazo).filter_by(project_id=project.id, employee_id=fel.employee.id).first()
        if tovabbi is not None:
            raise HTTPException(
                status_code=400,
                detail=f"{fel.employee.full_name} munkáját ezen a projekten maga is más számlázza - láncot nem lehet építeni.",
            )
    # És fordítva: aki már másokat számláz, annak ne lehessen számlázója.
    if db.query(ProjectSzamlazo).filter_by(project_id=project.id, szamlazo_employee_id=employee.id).first():
        raise HTTPException(
            status_code=400,
            detail=f"{employee.full_name} ezen a projekten mások munkáját számlázza - előbb azt kell feloldani.",
        )

    if sor is None:
        sor = ProjectSzamlazo(project_id=project.id, employee_id=employee.id)
        db.add(sor)
    sor.szamlazo_employee_id = fel.employee.id if fel.employee else None
    sor.szamlazo_vallalkozas_id = fel.vallalkozas.id if fel.vallalkozas else None
    sor.megjegyzes = payload.megjegyzes
    db.commit()
    return get_projekt_szamlazok(project.id, db, _user)


class VallalkozasValaszto(BaseModel):
    id: int
    nev: str
    adoszam: str | None = None


@router.get("", response_model=list[VallalkozasValaszto])
def list_valaszthato_vallalkozasok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az aktív cégek listája a választóhoz - akkor is kell, ha az adott
    embernél nincs tagsági javaslat (bárkit be lehet osztani bármelyik cég
    alá, a tagság csak javaslat)."""
    rows = db.query(Vallalkozas).filter(Vallalkozas.aktiv.is_(True)).order_by(Vallalkozas.nev).all()
    return [VallalkozasValaszto(id=v.id, nev=v.nev, adoszam=v.adoszam) for v in rows]
