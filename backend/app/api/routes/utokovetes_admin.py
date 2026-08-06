"""Utókövetés - összefoglaló admin nézet, ami EGY helyen mutatja egy diszpózott
projekthez tartozó teljes adminisztrációs "utóélet"-et: az eseti szerződések
állapotát (lásd subcontractor_contracts.py), a teljesítési igazolások
állapotát (lásd performance_certificates.py), és a forgatás utáni automatikus
kérdőívre (lásd public_utokovetes.py) beérkezett válaszokat. A tényleges
mentés/generálás/küldés/kihagyás műveletek továbbra is a saját (szerződés
ill. TIG) végpontjaikon futnak - ez a nézet csak összegyűjti és egy helyen
mutatja az állapotukat, hogy ne kelljen projektenként külön-külön két oldalt
végignézni."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.routes.performance_certificates import (
    _draft_info as _tig_draft_info,
    _load_tig_lookup,
    _tig_candidates,
    _tig_pending_employees,
    DraftInfo as TigDraftInfo,
)
from app.api.routes.subcontractor_contracts import (
    _draft_info as _contract_draft_info,
    _load_contract_lookup,
    _pending_employees,
    DraftInfo as ContractDraftInfo,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.contract import Contract
from app.models.employee import Employee, EmployeeType
from app.models.performance_certificate import PerformanceCertificate
from app.models.post_shoot_feedback import PostShootFeedback
from app.models.project import Project
from app.schemas.post_shoot_feedback import PostShootFeedbackRead

router = APIRouter(prefix="/utokovetes", tags=["utokovetes-admin"])

PAGE = "/utokovetes"


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


# A LISTA-nézet (list_utokovetes_overview) minden diszpózott projektre kiszámol
# három állapotot. Ha ezt projektenként külön lekérdezésekből tennénk, az
# projektszám x 3 adatbázis-fordulót jelentene - száz projektnél már érezhetően
# lassú, és a felület minden megnyitásakor újra lefut. Ezért a szerződés- és
# TIG-táblát EGYSZER olvassuk be az összes érintett emberre, és a lenti
# függvények ezt a két kész indexet kapják meg (a részletnézet, ahol egyetlen
# projektről van szó, továbbra is lekérdezhet magának - ott ez nem számít).


def _szerzodes_candidates(
    db: Session,
    project: Project,
    lookup: tuple[set[int], dict[tuple[int, int], Contract]] | None = None,
) -> tuple[int, int]:
    """(összes, függő) - hányan igényelnek eseti szerződést ezen a projekten
    (nem belsős és nincs keretszerződése), és ebből hányan függők."""
    if lookup is None:
        employee_ids = {e.id for e in project.crew if e.tipus != EmployeeType.BELSOS}
        lookup = _load_contract_lookup(db, employee_ids)
    keretszerzodes_ids, project_contracts = lookup
    total = sum(1 for e in project.crew if e.tipus != EmployeeType.BELSOS and e.id not in keretszerzodes_ids)
    pending = len(_pending_employees(project, keretszerzodes_ids, project_contracts))
    return total, pending


def _tig_state(
    db: Session,
    project: Project,
    szerzodes_done: bool,
    tig_lookup: dict[tuple[int, int], PerformanceCertificate] | None = None,
) -> tuple[bool, int, int]:
    """(tig_ready, összes, függő) - a TIG populáció a keretszerződéseseket IS
    tartalmazza (lásd performance_certificates.py _tig_candidates), csak akkor
    "kész" (tig_ready), ha a projekt teljes eseti szerződés fázisa lezárult."""
    candidates = _tig_candidates(project)
    total = len(candidates)
    if not candidates or not szerzodes_done:
        return False, total, total
    if tig_lookup is None:
        tig_lookup = _load_tig_lookup(db, {e.id for e in candidates})
    pending = _tig_pending_employees(project, tig_lookup)
    return True, total, len(pending)


def _kifizetes_state(
    db: Session,
    project: Project,
    tig_lookup: dict[tuple[int, int], PerformanceCertificate] | None = None,
) -> tuple[int, int]:
    """(összes, függő) - ki van-e fizetve mindenki, akinek fizetni kell.

    A populáció ugyanaz, mint a TIG-nél: minden NEM belsős stábtag, tehát a
    külsősök ÉS a keretszerződésesek is (a belsősök havi bérezésűek, nekik
    projektenként nincs kifizetés - a felhasználó kifejezett kérése).

    Akinek a TIG-je "Kihagyva", annak nincs mit kifizetni, ezért ki is marad a
    nevezőből - különben egy szándékosan kihagyott ember örökre "függőben"
    tartaná a projektet."""
    candidates = _tig_candidates(project)
    if not candidates:
        return 0, 0
    if tig_lookup is None:
        tig_lookup = _load_tig_lookup(db, {e.id for e in candidates})
    total = 0
    pending = 0
    for e in candidates:
        tig = tig_lookup.get((project.id, e.id))
        if tig is not None and tig.allapot == "Kihagyva":
            continue
        total += 1
        if tig is None or not tig.szamla_kifizetve:
            pending += 1
    return total, pending


class ProjectOverviewSummary(BaseModel):
    project_id: int
    project_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    szerzodes_osszes: int
    szerzodes_fuggo: int
    tig_ready: bool
    tig_osszes: int
    tig_fuggo: int
    kifizetes_osszes: int
    kifizetes_fuggo: int
    # Akkor és csak akkor teljesen kész a projekt, ha az adminisztráció mindhárom
    # fázisa lezárult ÉS mindenki meg is kapta a pénzét (lásd _kifizetes_state).
    kesz: bool
    visszajelzes_darab: int


@router.get("", response_model=list[ProjectOverviewSummary])
def list_utokovetes_overview(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Minden diszpózott projekt egy sorban, a szerződés/TIG/visszajelzés
    állapotával - nem csak a még függőket listázza (mint a két külön oldal),
    hanem MINDENT, hogy áttekintés is legyen, nem csak teendő-lista."""
    projects = (
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
        .options(selectinload(Project.crew), selectinload(Project.post_shoot_feedbacks))
        .order_by(Project.forgatas_datuma.desc().nullslast())
        .all()
    )
    # Két lekérdezés az egész listához, nem projektenként három (lásd a fenti
    # megjegyzést a _szerzodes_candidates fölött).
    minden_employee_id = {e.id for p in projects for e in p.crew if e.tipus != EmployeeType.BELSOS}
    szerzodes_lookup = _load_contract_lookup(db, minden_employee_id)
    tig_lookup = _load_tig_lookup(db, minden_employee_id)

    result: list[ProjectOverviewSummary] = []
    for p in projects:
        szerzodes_osszes, szerzodes_fuggo = _szerzodes_candidates(db, p, szerzodes_lookup)
        tig_ready, tig_osszes, tig_fuggo = _tig_state(db, p, szerzodes_fuggo == 0, tig_lookup)
        kifizetes_osszes, kifizetes_fuggo = _kifizetes_state(db, p, tig_lookup)
        result.append(
            ProjectOverviewSummary(
                project_id=p.id,
                project_nev=p.nev,
                projektkod=p.projektkod_szoveg,
                forgatas_datuma=p.forgatas_datuma,
                forgatas_datuma_vege=p.forgatas_datuma_vege,
                szerzodes_osszes=szerzodes_osszes,
                szerzodes_fuggo=szerzodes_fuggo,
                tig_ready=tig_ready,
                tig_osszes=tig_osszes,
                tig_fuggo=tig_fuggo,
                kifizetes_osszes=kifizetes_osszes,
                kifizetes_fuggo=kifizetes_fuggo,
                kesz=szerzodes_fuggo == 0 and tig_fuggo == 0 and kifizetes_fuggo == 0,
                visszajelzes_darab=len(p.post_shoot_feedbacks),
            )
        )
    return result


class ContractStatusInfo(BaseModel):
    id: int
    full_name: str
    email: str | None
    draft: ContractDraftInfo | None


class TigStatusInfo(BaseModel):
    id: int
    full_name: str
    email: str | None
    draft: TigDraftInfo | None
    # A TIG kiküldése utáni lépés: fel van-e töltve a számla és ki van-e fizetve
    # (lásd models/performance_certificate.py) - enélkül a projekt nincs kész.
    szamla_kifizetve: bool = False
    van_szamla: bool = False


class ProjectOverviewDetail(BaseModel):
    project_id: int
    project_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    szerzodesek: list[ContractStatusInfo]
    tig_ready: bool
    teljesitesi_igazolasok: list[TigStatusInfo]
    kifizetes_osszes: int
    kifizetes_fuggo: int
    kesz: bool
    visszajelzesek: list[PostShootFeedbackRead]


@router.get("/{project_id}", response_model=ProjectOverviewDetail)
def get_utokovetes_detail(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    project = _get_project_or_404(db, project_id)

    employee_ids = {e.id for e in project.crew if e.tipus != EmployeeType.BELSOS}
    keretszerzodes_ids, project_contracts = _load_contract_lookup(db, employee_ids)
    szerzodesek = [
        ContractStatusInfo(id=e.id, full_name=e.full_name, email=e.email, draft=_contract_draft_info(project_contracts.get((project.id, e.id))))
        for e in project.crew
        if e.tipus != EmployeeType.BELSOS and e.id not in keretszerzodes_ids
    ]
    szerzodes_done = len(_pending_employees(project, keretszerzodes_ids, project_contracts)) == 0

    tig_ready = False
    teljesitesi_igazolasok: list[TigStatusInfo] = []
    if szerzodes_done:
        candidates = _tig_candidates(project)
        tig_ready = bool(candidates)
        tig_lookup = _load_tig_lookup(db, {e.id for e in candidates})
        for e in candidates:
            tig = tig_lookup.get((project.id, e.id))
            teljesitesi_igazolasok.append(
                TigStatusInfo(
                    id=e.id,
                    full_name=e.full_name,
                    email=e.email,
                    draft=_tig_draft_info(tig),
                    szamla_kifizetve=bool(tig and tig.szamla_kifizetve),
                    van_szamla=bool(tig and tig.invoices),
                )
            )
    kifizetes_osszes, kifizetes_fuggo = _kifizetes_state(db, project)
    tig_fuggo = len(_tig_pending_employees(project, _load_tig_lookup(db, {e.id for e in _tig_candidates(project)}))) if szerzodes_done else 1

    feedbacks = (
        db.query(PostShootFeedback)
        .filter(PostShootFeedback.project_id == project.id)
        .order_by(PostShootFeedback.created_at.desc())
        .all()
    )

    return ProjectOverviewDetail(
        project_id=project.id,
        project_nev=project.nev,
        projektkod=project.projektkod_szoveg,
        forgatas_datuma=project.forgatas_datuma,
        forgatas_datuma_vege=project.forgatas_datuma_vege,
        szerzodesek=szerzodesek,
        tig_ready=tig_ready,
        teljesitesi_igazolasok=teljesitesi_igazolasok,
        kifizetes_osszes=kifizetes_osszes,
        kifizetes_fuggo=kifizetes_fuggo,
        kesz=szerzodes_done and tig_fuggo == 0 and kifizetes_fuggo == 0,
        visszajelzesek=[PostShootFeedbackRead.model_validate(f) for f in feedbacks],
    )
