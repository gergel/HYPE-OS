"""Utókövetés - összefoglaló admin nézet, ami EGY helyen mutatja egy diszpózott
projekthez tartozó teljes adminisztrációs "utóélet"-et: az eseti szerződések
állapotát (lásd subcontractor_contracts.py), a teljesítési igazolások
állapotát (lásd performance_certificates.py), és a forgatás utáni automatikus
kérdőívre (lásd public_utokovetes.py) beérkezett válaszokat. A tényleges
mentés/generálás/küldés/kihagyás műveletek továbbra is a saját (szerződés
ill. TIG) végpontjaikon futnak - ez a nézet csak összegyűjti és egy helyen
mutatja az állapotukat, hogy ne kelljen projektenként külön-külön két oldalt
végignézni.

A sorok SZÁMLÁZÓ FELENKÉNT állnak, nem emberenként: ha egy projekten több
stábtag munkáját ugyanaz a fél (másik ember vagy egy cég) számlázza, egyetlen
szerződés és egyetlen TIG kell - lásd services/szamlazo.py."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.routes.performance_certificates import (
    _draft_info as _tig_draft_info,
    _load_tig_lookup,
    _tig_candidates,
    _tig_pending_csoportok,
    tig_csoportok,
    DraftInfo as TigDraftInfo,
    TigLookup,
)
from app.api.routes.subcontractor_contracts import (
    _draft_info as _contract_draft_info,
    _mentesul_keretszerzodessel,
    _pending_csoportok,
    _szamlazo_csoportok,
    load_szerzodes_kornyezet,
    DraftInfo as ContractDraftInfo,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.post_shoot_feedback import PostShootFeedback
from app.models.project import Project
from app.models.project_szamlazo import ProjectSzamlazo
from app.schemas.post_shoot_feedback import PostShootFeedbackRead
from app.services.szamlazo import SzamlazoCsoport

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
# TIG-táblát EGYSZER olvassuk be az összes érintett projektre, és a lenti
# függvények ezt a kész indexet kapják meg.


def _szerzodes_candidates(
    project: Project,
    keretszerzodesek: dict[str, list[Contract]],
    project_contracts: dict[tuple[int, str], Contract],
    felulirasok: dict[tuple[int, int], ProjectSzamlazo],
) -> tuple[int, int, list[tuple[SzamlazoCsoport, Contract | None]]]:
    """(összes, függő, függő sorok) - hány SZÁMLÁZÓ FÉL igényel eseti
    szerződést ezen a projekten, és ebből hány van még hátra.

    Az "összes" azért nem a stáblétszám, mert egy fél több ember munkájáról is
    szerződhet egyben."""
    csoportok = _szamlazo_csoportok(project, felulirasok)
    total = sum(
        1
        for cs in csoportok
        if not _mentesul_keretszerzodessel(keretszerzodesek.get(cs.kulcs, []), project.forgatas_datuma)
    )
    pending = _pending_csoportok(project, keretszerzodesek, project_contracts, felulirasok)
    return total, len(pending), pending


def _tig_state(
    project: Project,
    szerzodes_done: bool,
    felulirasok: dict[tuple[int, int], ProjectSzamlazo],
    tig_lookup: TigLookup,
) -> tuple[bool, int, int]:
    """(tig_ready, összes, függő) - a TIG populáció a keretszerződéseseket IS
    tartalmazza (lásd performance_certificates.py _tig_candidates), csak akkor
    "kész" (tig_ready), ha a projekt teljes eseti szerződés fázisa lezárult."""
    if not _tig_candidates(project):
        return False, 0, 0
    csoportok = tig_csoportok(project, felulirasok)
    total = len(csoportok)
    if not szerzodes_done:
        return False, total, total
    return True, total, len(_tig_pending_csoportok(project, csoportok, tig_lookup))


def _kifizetes_state(
    project: Project,
    felulirasok: dict[tuple[int, int], ProjectSzamlazo],
    tig_lookup: TigLookup,
) -> tuple[int, int]:
    """(összes, függő) - ki van-e fizetve mindenki, akinek fizetni kell.

    A populáció ugyanaz, mint a TIG-nél: minden nem belsős munkát számlázó fél
    (a belsősök havi bérezésűek, nekik projektenként nincs kifizetés - a
    felhasználó kifejezett kérése).

    Akinek a TIG-je "Kihagyva", annak nincs mit kifizetni, ezért ki is marad a
    nevezőből - különben egy szándékosan kihagyott fél örökre "függőben"
    tartaná a projektet."""
    _, fel_tig = tig_lookup
    csoportok = tig_csoportok(project, felulirasok)
    if not csoportok:
        return 0, 0
    total = 0
    pending = 0
    for csoport in csoportok:
        tig = fel_tig.get((project.id, csoport.kulcs))
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
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projects)
    tig_lookup = _load_tig_lookup(db, {p.id for p in projects})

    result: list[ProjectOverviewSummary] = []
    for p in projects:
        szerzodes_osszes, szerzodes_fuggo, _ = _szerzodes_candidates(
            p, keretszerzodesek, project_contracts, felulirasok
        )
        tig_ready, tig_osszes, tig_fuggo = _tig_state(p, szerzodes_fuggo == 0, felulirasok, tig_lookup)
        kifizetes_osszes, kifizetes_fuggo = _kifizetes_state(p, felulirasok, tig_lookup)
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


class LefedettEmber(BaseModel):
    id: int
    full_name: str


class ContractStatusInfo(BaseModel):
    #: A régi felület kedvéért az ember azonosítója (cégnél 0); a műveletek a
    #: `szamlazo` kulccsal címeznek.
    id: int
    szamlazo: str
    full_name: str
    #: "Ladányi Máté (Balla Berci helyett is)"
    cimke: str
    lefedettek: list[LefedettEmber] = []
    email: str | None
    draft: ContractDraftInfo | None


class TigStatusInfo(BaseModel):
    id: int
    szamlazo: str
    full_name: str
    cimke: str
    lefedettek: list[LefedettEmber] = []
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


def _lefedettek(csoport: SzamlazoCsoport) -> list[LefedettEmber]:
    return [LefedettEmber(id=t.id, full_name=t.full_name) for t in csoport.tagok]


@router.get("/{project_id}", response_model=ProjectOverviewDetail)
def get_utokovetes_detail(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    project = _get_project_or_404(db, project_id)

    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, [project])
    _, szerzodes_fuggo, pending_szerzodesek = _szerzodes_candidates(
        project, keretszerzodesek, project_contracts, felulirasok
    )
    szerzodesek = [
        ContractStatusInfo(
            id=csoport.fel.employee.id if csoport.fel.employee else 0,
            szamlazo=csoport.kulcs,
            full_name=csoport.fel.nev,
            cimke=csoport.cimke(),
            lefedettek=_lefedettek(csoport),
            email=csoport.fel.email,
            draft=_contract_draft_info(existing),
        )
        for csoport, existing in pending_szerzodesek
    ]
    szerzodes_done = szerzodes_fuggo == 0

    tig_lookup = _load_tig_lookup(db, {project.id})
    _, fel_tig = tig_lookup
    tig_ready = False
    teljesitesi_igazolasok: list[TigStatusInfo] = []
    if szerzodes_done:
        csoportok = tig_csoportok(project, felulirasok)
        tig_ready = bool(csoportok)
        for csoport in csoportok:
            tig = fel_tig.get((project.id, csoport.kulcs))
            teljesitesi_igazolasok.append(
                TigStatusInfo(
                    id=csoport.fel.employee.id if csoport.fel.employee else 0,
                    szamlazo=csoport.kulcs,
                    full_name=csoport.fel.nev,
                    cimke=csoport.cimke(),
                    lefedettek=_lefedettek(csoport),
                    email=csoport.fel.email,
                    draft=_tig_draft_info(tig),
                    szamla_kifizetve=bool(tig and tig.szamla_kifizetve),
                    van_szamla=bool(tig and tig.invoices),
                )
            )
    kifizetes_osszes, kifizetes_fuggo = _kifizetes_state(project, felulirasok, tig_lookup)
    _, _, tig_fuggo = _tig_state(project, szerzodes_done, felulirasok, tig_lookup)

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
