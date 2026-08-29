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
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.routes.performance_certificates import (
    _draft_info as _tig_draft_info,
    _load_tig_lookup,
    _load_tig_lookup_projektkodon,
    _tig_candidates,
    _tig_pending_csoportok,
    _tig_pending_csoportok_projektkodon,
    projektkodok_alvallalkozoi_kiadassal,
    tig_csoportok,
    tig_keszitheto_csoportok,
    tig_keszitheto_csoportok_projektkodon,
    DraftInfo as TigDraftInfo,
    TigLookup,
    TigLookupProjektkod,
)
from app.api.routes.subcontractor_contracts import (
    _draft_info as _contract_draft_info,
    _mentesul_keretszerzodessel,
    _pending_csoportok,
    _pending_csoportok_projektkodon,
    _szamlazo_csoportok,
    alairasra_varo_csoportok,
    alairasra_varo_csoportok_projektkodon,
    load_szerzodes_kornyezet,
    load_szerzodes_kornyezet_projektkodon,
    szamlazo_csoportok_projektkodon,
    szerzodest_igenylo_emberek_projektkodon,
    DraftInfo as ContractDraftInfo,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.post_shoot_feedback import PostShootFeedback
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_szamlazo import ProjectSzamlazo
from app.schemas.post_shoot_feedback import PostShootFeedbackRead
from app.services import papirozas_hatokor
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
    keretszerzodesek: dict[str, list[Contract]],
    project_contracts: dict[tuple[int, str], Contract],
    felulirasok: dict[tuple[int, int], ProjectSzamlazo],
    tig_lookup: TigLookup,
) -> tuple[bool, int, int]:
    """(tig_ready, összes, függő) - a TIG populáció a keretszerződéseseket IS
    tartalmazza (lásd performance_certificates.py _tig_candidates).

    A "kész" állapot FELENKÉNT dől el: amint egy félnek megvan a szerződése
    (vagy keretszerződés mentesíti), róla azonnal készíthető TIG - nem kell
    megvárni, hogy a projekt összes szereplőjének meglegyen a papírja. A
    `tig_fuggo` így csak azokat számolja, akikről MÁR lehetne TIG-et készíteni,
    de még nincs; akinél a szerződés is hiányzik, az a szerződés-oszlopban vár."""
    if not _tig_candidates(project, felulirasok):
        return False, 0, 0
    csoportok = tig_csoportok(project, felulirasok)
    total = len(csoportok)
    keszitheto = tig_keszitheto_csoportok(project, felulirasok, keretszerzodesek, project_contracts)
    if not keszitheto:
        # Mindenki szerződésre vár - de akinek a TIG-jét KIHAGYTUK, az nem
        # függő: a kihagyás önálló lépés, nem kell hozzá szerződés (lásd
        # routes/performance_certificates.skip_tig).
        return False, total, len(_tig_pending_csoportok(project, csoportok, tig_lookup))
    return True, total, len(_tig_pending_csoportok(project, keszitheto, tig_lookup))


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
        # Akinél a SZÁMLA-lépést hagytuk ki (a papír megvan, de pénz nem megy
        # ki rá - máshol számolták el, elengedték), annál sincs mit várni:
        # különben örökre függőben tartaná a projektet, pedig nincs rajta
        # teendő (lásd routes/performance_certificates.skip_szamla).
        if tig is not None and tig.szamla_kihagyva:
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
    #: Hány kiküldött szerződést várunk még vissza ALÁÍRVA (lásd
    #: subcontractor_contracts.alairasra_varo_csoportok).
    alairas_varo: int
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
    hanem MINDENT, hogy áttekintés is legyen, nem csak teendő-lista.

    Azok a Projectek is bekerülnek, amikhez nem tartozik kiküldött diszpó, de
    van hozzájuk kötött alvállalkozói kiadás (lásd
    subcontractor_contracts.list_pending_projects) - egy tisztán ügynökségi
    feladatnál (nincs forgatás) ez az egyetlen jel, hogy szerződés/TIG kell."""
    projects = papirozas_hatokor.papirozando_projektek(
        db.query(Project)
        .filter(or_(Project.diszpo == "Kiküldve", Project.alvallalkozo_kiadasok.any()))
        .options(
            selectinload(Project.crew),
            selectinload(Project.alvallalkozo_kiadasok).selectinload(Expense.employee),
            selectinload(Project.project_code),
            selectinload(Project.post_shoot_feedbacks),
        )
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
        tig_ready, tig_osszes, tig_fuggo = _tig_state(
            p, keretszerzodesek, project_contracts, felulirasok, tig_lookup
        )
        kifizetes_osszes, kifizetes_fuggo = _kifizetes_state(p, felulirasok, tig_lookup)
        alairas_varo = len(alairasra_varo_csoportok(p, keretszerzodesek, project_contracts, felulirasok))
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
                alairas_varo=alairas_varo,
                kifizetes_osszes=kifizetes_osszes,
                kifizetes_fuggo=kifizetes_fuggo,
                # A kiküldött szerződés még nem lezárt ügy: amíg aláírva vissza
                # nem érkezett, a projekt sem kész.
                kesz=szerzodes_fuggo == 0
                and tig_fuggo == 0
                and kifizetes_fuggo == 0
                and alairas_varo == 0,
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
    #: A SZÁMLA-lépés kihagyva: ide nem jön se számla, se kifizetés. Független
    #: a TIG-től - kihagyni akkor is lehet, ha TIG még nincs (lásd
    #: routes/performance_certificates.skip_szamla).
    szamla_kihagyva: bool = False
    #: Készíthető-e már TIG erről a félről (megvan a szerződése, vagy keret
    #: fedi). Ahol nem, ott a felületen csak a KIHAGYÁS érhető el.
    tig_keszitheto: bool = True


class ProjectOverviewDetail(BaseModel):
    project_id: int
    project_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    szerzodesek: list[ContractStatusInfo]
    tig_ready: bool
    teljesitesi_igazolasok: list[TigStatusInfo]
    #: Hány kiküldött szerződést várunk még vissza aláírva.
    alairas_varo: int
    kifizetes_osszes: int
    kifizetes_fuggo: int
    kesz: bool
    visszajelzesek: list[PostShootFeedbackRead]


def _lefedettek(csoport: SzamlazoCsoport) -> list[LefedettEmber]:
    return [LefedettEmber(id=t.id, full_name=t.full_name) for t in csoport.tagok]


class ProjectCodeOverviewSummary(BaseModel):
    project_code_id: int
    projektkod: str
    project_nev: str | None
    szerzodes_osszes: int
    szerzodes_fuggo: int
    tig_ready: bool
    tig_osszes: int
    tig_fuggo: int
    #: Hány kiküldött szerződést várunk még vissza ALÁÍRVA (lásd
    #: subcontractor_contracts.alairasra_varo_csoportok_projektkodon).
    alairas_varo: int
    kifizetes_osszes: int
    kifizetes_fuggo: int
    kesz: bool


@router.get("/projektkodok", response_model=list[ProjectCodeOverviewSummary])
def list_utokovetes_overview_projektkodok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Lásd list_utokovetes_overview (forgatás-alapú megfelelője) - azok a
    projektkódok, amiken FORGATÁS NÉLKÜL van alvállalkozói kiadás."""
    project_codes = [
        pk for pk in projektkodok_alvallalkozoi_kiadassal(db) if szerzodest_igenylo_emberek_projektkodon(pk)
    ]
    # Egyszerre, az ÖSSZES projektkódra - lásd load_szerzodes_kornyezet
    # (forgatás-alapú megfelelője): ciklusban hívva projektkódonként külön
    # lekérdezés-köteg futna, ami sok projektkódnál érezhető lassulás.
    keretszerzodesek, project_code_contracts = load_szerzodes_kornyezet_projektkodon(db, project_codes)
    tig_lookup = _load_tig_lookup_projektkodon(db, {pk.id for pk in project_codes})
    result: list[ProjectCodeOverviewSummary] = []
    for pk in project_codes:
        szerzodes_osszes, szerzodes_fuggo = _szerzodes_candidates_projektkodon(
            pk, keretszerzodesek, project_code_contracts
        )
        tig_ready, tig_osszes, tig_fuggo = _tig_state_projektkodon(
            pk, keretszerzodesek, project_code_contracts, tig_lookup
        )
        kifizetes_osszes, kifizetes_fuggo = _kifizetes_state_projektkodon(pk, tig_lookup)
        alairas_varo = len(alairasra_varo_csoportok_projektkodon(pk, keretszerzodesek, project_code_contracts))
        result.append(
            ProjectCodeOverviewSummary(
                project_code_id=pk.id,
                projektkod=pk.projektkod,
                project_nev=pk.project_nev,
                szerzodes_osszes=szerzodes_osszes,
                szerzodes_fuggo=szerzodes_fuggo,
                tig_ready=tig_ready,
                tig_osszes=tig_osszes,
                tig_fuggo=tig_fuggo,
                alairas_varo=alairas_varo,
                kifizetes_osszes=kifizetes_osszes,
                kifizetes_fuggo=kifizetes_fuggo,
                # A kiküldött szerződés még nem lezárt ügy: amíg aláírva vissza
                # nem érkezett, a projektkód sem kész.
                kesz=szerzodes_fuggo == 0 and tig_fuggo == 0 and kifizetes_fuggo == 0 and alairas_varo == 0,
            )
        )
    return result


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
    # A TIG-oszlopban azok a felek jelennek meg, akikről MÁR készíthető TIG:
    # akinek megvan az eseti szerződése, vagy akit keretszerződés mentesít. Aki
    # még szerződésre vár, az a szerződés-oszlopban látszik - így egy késlekedő
    # stábtag nem tartja fel a többiek papírozását.
    keszitheto = tig_keszitheto_csoportok(project, felulirasok, keretszerzodesek, project_contracts)
    tig_ready = bool(keszitheto)
    keszitheto_kulcsok = {cs.kulcs for cs in keszitheto}
    # MINDEN számlázó fél, nem csak akiről már készíthető TIG: a kifizetés
    # populációja is a teljes lista (lásd _kifizetes_state), tehát ha itt csak
    # a szerződés-készeket mutatnánk, a kártya többet mondana, mint a lista
    # alatta. A szerződésre várókon a felület csak a KIHAGYÁST kínálja.
    teljesitesi_igazolasok: list[TigStatusInfo] = []
    for csoport in tig_csoportok(project, felulirasok):
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
                szamla_kihagyva=bool(tig and tig.szamla_kihagyva),
                tig_keszitheto=csoport.kulcs in keszitheto_kulcsok,
            )
        )
    kifizetes_osszes, kifizetes_fuggo = _kifizetes_state(project, felulirasok, tig_lookup)
    _, _, tig_fuggo = _tig_state(project, keretszerzodesek, project_contracts, felulirasok, tig_lookup)
    alairas_varo = len(alairasra_varo_csoportok(project, keretszerzodesek, project_contracts, felulirasok))

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
        alairas_varo=alairas_varo,
        kifizetes_osszes=kifizetes_osszes,
        kifizetes_fuggo=kifizetes_fuggo,
        kesz=szerzodes_done and tig_fuggo == 0 and kifizetes_fuggo == 0 and alairas_varo == 0,
        visszajelzesek=[PostShootFeedbackRead.model_validate(f) for f in feedbacks],
    )


# ═══════════════════════════════════════════════════════════════════════════
# PROJEKTKÓD-SZINTŰ ÁG: forgatás nélküli alvállalkozói kiadások áttekintője
# ═══════════════════════════════════════════════════════════════════════════
#
# Lásd subcontractor_contracts.py és performance_certificates.py azonos című
# szakaszait. UGYANOLYAN négy fázisa van, mint a forgatás-alapú áttekintőnek
# (szerződés, TIG, aláírás, kifizetés) - csak egyszerűbb bennük a populáció,
# mert nincs tétel-rendszer és nincs "ki számláz kiért" felülírás ezen az
# ágon: egy projektkódon mindenki önmagáért számláz.


def _szerzodes_candidates_projektkodon(
    projektkod: ProjectCode,
    keretszerzodesek: dict[str, list[Contract]],
    project_code_contracts: dict[tuple[int, str], Contract],
) -> tuple[int, int]:
    """Lásd _szerzodes_candidates (forgatás-alapú megfelelője)."""
    csoportok = szamlazo_csoportok_projektkodon(projektkod)
    total = sum(
        1
        for cs in csoportok
        if not _mentesul_keretszerzodessel(keretszerzodesek.get(cs.kulcs, []), projektkod.datum)
    )
    pending = _pending_csoportok_projektkodon(projektkod, keretszerzodesek, project_code_contracts)
    return total, len(pending)


def _tig_state_projektkodon(
    projektkod: ProjectCode,
    keretszerzodesek: dict[str, list[Contract]],
    project_code_contracts: dict[tuple[int, str], Contract],
    tig_lookup: TigLookupProjektkod,
) -> tuple[bool, int, int]:
    """Lásd _tig_state (forgatás-alapú megfelelője)."""
    if not szerzodest_igenylo_emberek_projektkodon(projektkod):
        return False, 0, 0
    csoportok = szamlazo_csoportok_projektkodon(projektkod)
    total = len(csoportok)
    keszitheto = tig_keszitheto_csoportok_projektkodon(projektkod, keretszerzodesek, project_code_contracts)
    if not keszitheto:
        return False, total, len(_tig_pending_csoportok_projektkodon(projektkod, csoportok, tig_lookup))
    return True, total, len(_tig_pending_csoportok_projektkodon(projektkod, keszitheto, tig_lookup))

def _kifizetes_state_projektkodon(
    projektkod: ProjectCode,
    tig_lookup: TigLookupProjektkod,
) -> tuple[int, int]:
    """Lásd _kifizetes_state (forgatás-alapú megfelelője)."""
    _, fel_tig = tig_lookup
    csoportok = szamlazo_csoportok_projektkodon(projektkod)
    if not csoportok:
        return 0, 0
    total = 0
    pending = 0
    for csoport in csoportok:
        tig = fel_tig.get((projektkod.id, csoport.kulcs))
        if tig is not None and tig.allapot == "Kihagyva":
            continue
        if tig is not None and tig.szamla_kihagyva:
            continue
        total += 1
        if tig is None or not tig.szamla_kifizetve:
            pending += 1
    return total, pending
