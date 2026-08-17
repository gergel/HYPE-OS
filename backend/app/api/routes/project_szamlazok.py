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
from sqlalchemy import or_, select
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
    #: Projekt kiadásként van elszámolva, nem résztvevőként - ilyenkor nem kell
    #: tőle sem szerződés, sem TIG (lásd models/project_szamlazo.py).
    kiadaskent_elszamolva: bool = False
    #: Hova és miért került a kiadásba - a jelöléshez kötelező.
    kiadas_megjegyzes: str | None = None
    #: Mennyiért vállalja ezt a napot (nettó) és mi van benne - a diszpó
    #: írásakor lebeszélt díj (lásd models/project_szamlazo.py).
    megbeszelt_dij: float | None = None
    dij_megjegyzes: str | None = None
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


class KiadaskentIn(BaseModel):
    kiadaskent_elszamolva: bool
    #: Hova és miért került a kiadásba. Bekapcsoláskor kötelező.
    kiadas_megjegyzes: str | None = None


class MegbeszeltDijIn(BaseModel):
    """Mennyiért vállalja ez az ember ezt a napot.

    Üres összeg = nincs (vagy már nincs) lebeszélt díj: a felvételkor
    kihagyható, később törölhető."""

    megbeszelt_dij: float | None = None
    dij_megjegyzes: str | None = None


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
                kiadaskent_elszamolva=bool(sor.kiadaskent_elszamolva) if sor else False,
                kiadas_megjegyzes=sor.kiadas_megjegyzes if sor else None,
                megbeszelt_dij=float(sor.megbeszelt_dij) if sor and sor.megbeszelt_dij is not None else None,
                dij_megjegyzes=sor.dij_megjegyzes if sor else None,
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


def _ures_sor(sor: ProjectSzamlazo) -> bool:
    """Hordoz-e még bármit ez a sor?

    Egy soron több, egymástól független beállítás él (számlázó fél, kiadásként
    elszámolva, megbeszélt díj) - az egyik visszavonása nem törölheti a
    többit, üres nyomot viszont ne hagyjunk magunk után."""
    return (
        sor.szamlazo_employee_id is None
        and sor.szamlazo_vallalkozas_id is None
        and not sor.kiadaskent_elszamolva
        and sor.megbeszelt_dij is None
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

    # Üres érték vagy önmaga: nincs mit felülírni, a sor törölhető - DE csak
    # akkor, ha nem hordoz más beállítást is. A "kiadásként elszámolva" jelölő
    # és a megbeszélt díj ugyanezen a soron él, azokat egy számlázó-visszaállítás
    # nem törölheti el.
    if not kulcs or kulcs == f"e{employee.id}":
        if sor is not None:
            sor.szamlazo_employee_id = None
            sor.szamlazo_vallalkozas_id = None
            sor.megjegyzes = payload.megjegyzes
            if _ures_sor(sor):
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
        # Csak a VALÓDI felülírás számít láncnak: a soron más beállítás is
        # élhet (megbeszélt díj, kiadásként elszámolva), attól még ő maga
        # számláz.
        tovabbi = (
            db.query(ProjectSzamlazo)
            .filter(
                ProjectSzamlazo.project_id == project.id,
                ProjectSzamlazo.employee_id == fel.employee.id,
                or_(
                    ProjectSzamlazo.szamlazo_employee_id.is_not(None),
                    ProjectSzamlazo.szamlazo_vallalkozas_id.is_not(None),
                ),
            )
            .first()
        )
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


@router.put("/{project_id}/{employee_id}/kiadaskent", response_model=ProjektSzamlazoNezet)
def set_kiadaskent(
    project_id: int,
    employee_id: int,
    payload: KiadaskentIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Ez a stábtag PROJEKT KIADÁSKÉNT van elszámolva, nem résztvevőként.

    Tipikus eset: valaki technikát hozott, és a díja a bérleti árban már benne
    van - tőle nincs mit szerződni és igazolni, mert nem a munkájáért fizetünk
    külön. Stábtag attól még marad: kap diszpót, rajta van a projekten.

    A jelöléshez KÖTELEZŐ megadni, hova és miért került a kiadásba: enélkül a
    jelölés csak annyit mondana, hogy tőle nem kell papír, azt nem, hogy hol
    keressük a pénzt - és pont ez a kérdés fél év múlva vagy egy könyvelői
    egyeztetésnél.

    Utólag is állítható, mindkét irányba: sokszor csak a számla megérkezésekor
    derül ki, hogy valakinek a díja már egy másik tételben szerepel.

    Ha már készült róla papír, előbb azt kell rendezni - különben egy kiküldött
    szerződés vagy TIG lógna a levegőben olyasvalakinél, aki a rendszer szerint
    nem is igényel papírt."""
    project = _get_project_or_404(db, project_id)
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található")
    if employee not in project.crew:
        raise HTTPException(status_code=400, detail="Ez a munkatárs nincs a projekt stábjában.")
    indok = (payload.kiadas_megjegyzes or "").strip()
    if payload.kiadaskent_elszamolva and not indok:
        raise HTTPException(
            status_code=400,
            detail="Add meg, hova és miért került a kiadásba - enélkül nem derül ki, hol keressük a pénzt.",
        )
    if payload.kiadaskent_elszamolva and _van_papir(db, project.id, employee.id):
        raise HTTPException(
            status_code=400,
            detail="Erről a munkáról már készült TIG - előbb azt kell törölni, csak utána jelölhető kiadásként.",
        )

    sor = db.query(ProjectSzamlazo).filter_by(project_id=project.id, employee_id=employee.id).first()
    if sor is None:
        if not payload.kiadaskent_elszamolva:
            return get_projekt_szamlazok(project.id, db, _user)
        sor = ProjectSzamlazo(project_id=project.id, employee_id=employee.id)
        db.add(sor)
    sor.kiadaskent_elszamolva = payload.kiadaskent_elszamolva
    # A magyarázat a jelöléssel együtt él: kikapcsoláskor nincs mit magyarázni.
    sor.kiadas_megjegyzes = indok if payload.kiadaskent_elszamolva else None
    # Ha a sor már semmit nem hordoz, ne maradjon üres nyoma.
    if _ures_sor(sor):
        db.delete(sor)
    db.commit()
    return get_projekt_szamlazok(project.id, db, _user)


@router.put("/{project_id}/{employee_id}/dij", response_model=ProjektSzamlazoNezet)
def set_megbeszelt_dij(
    project_id: int,
    employee_id: int,
    payload: MegbeszeltDijIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Mennyiért vállalja ez az ember EZT a napot - a diszpó írásakor lebeszélt
    nettó díj.

    A stábtag felvételekor kérdezzük meg, mert ott dől el: aki beosztja, az
    beszéli meg vele. A szerződést és a TIG-et viszont hetekkel később, más
    ember adminisztrálja, akinek pont ez az összeg kell a papírra - ha itt meg
    van adva, a piszkozataik automatikusan ezzel nyílnak meg (lásd
    services/megbeszelt_dij.py).

    Kihagyható és utólag is megadható: nem minden stábtaggal beszélnek le előre
    fix díjat. Üres összeggel törölhető.

    Ez a díj MEGÁLLAPODÁS, nem kifizetés: a projekt költségébe semmi nem kerül
    belőle - az továbbra is a TIG-eken és a Kiadás sorokon áll."""
    project = _get_project_or_404(db, project_id)
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="A munkatárs nem található")
    if employee not in project.crew:
        raise HTTPException(status_code=400, detail="Ez a munkatárs nincs a projekt stábjában.")
    if employee.tipus == EmployeeType.BELSOS:
        raise HTTPException(
            status_code=400,
            detail="Belsős munkatárs havi bérezésű - nála nincs projektenkénti napidíj.",
        )
    if payload.megbeszelt_dij is not None and payload.megbeszelt_dij < 0:
        raise HTTPException(status_code=400, detail="A díj nem lehet negatív.")

    sor = db.query(ProjectSzamlazo).filter_by(project_id=project.id, employee_id=employee.id).first()
    if sor is None:
        if payload.megbeszelt_dij is None:
            return get_projekt_szamlazok(project.id, db, _user)
        sor = ProjectSzamlazo(project_id=project.id, employee_id=employee.id)
        db.add(sor)
    sor.megbeszelt_dij = payload.megbeszelt_dij
    # A magyarázat a díjjal együtt él: összeg nélkül nincs mit magyarázni.
    megjegyzes = (payload.dij_megjegyzes or "").strip()
    sor.dij_megjegyzes = (megjegyzes or None) if payload.megbeszelt_dij is not None else None
    if _ures_sor(sor):
        db.delete(sor)
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
