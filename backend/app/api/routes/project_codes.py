from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.crud_router import build_crud_router
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.schemas.project_code import ProjectCodeCreate, ProjectCodeRead, ProjectCodeUpdate


def _papir_kapcsolok_ellenorzese(obj: ProjectCode, data: dict, _db: Session) -> None:
    """A "papír nélkül elszámolt" jelöléshez KÖTELEZŐ az indok.

    A jelölés kiveszi a projektkódot a papírozandók közül (lásd
    services/megrendeloi_papir.papirt_igenyel) - ha nem tudjuk, miért, akkor
    fél év múlva csak annyi látszik, hogy erről az egy munkáról nincs se
    szerződés, se TIG, és nem lesz mihez kötni.

    A PATCH tipikusan csak a változó mezőt küldi, ezért a beküldött értéket és
    a rekord mostani állapotát EGYÜTT kell nézni: az indok jöhet ugyanabban a
    kérésben, de lehet, hogy már korábban rögzítették."""
    if "papir_nelkul" not in data and "papir_nelkul_indoka" not in data:
        return
    papir_nelkul = data.get("papir_nelkul", obj.papir_nelkul)
    if not papir_nelkul:
        return
    indok = data.get("papir_nelkul_indoka", obj.papir_nelkul_indoka)
    if not (indok or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A papír nélküli elszámoláshoz meg kell adni az okát.",
        )


router = build_crud_router(
    model=ProjectCode,
    create_schema=ProjectCodeCreate,
    update_schema=ProjectCodeUpdate,
    read_schema=ProjectCodeRead,
    prefix="/project-codes",
    tags=["project-codes"],
    # Külön jogosultsági hatókör, NEM ugyanaz, mint a Projekteké (lásd
    # projects.py page="/projektek") - a felhasználó explicit kérése, hogy
    # a Project Code-okhoz csak külön, kifejezett jogosultsággal lehessen
    # hozzáférni, ne automatikusan a Projektek jogosultsággal együtt.
    page="/projektek/project-kodok",
    entity_type="projectCode",
    before_update=_papir_kapcsolok_ellenorzese,
    # A ProjectCodeRead számított mezői (osszes_koltseg, becsult_profit)
    # végigjárják a kiadásokat, az utómunkákat és a bevételeket. Eager load
    # nélkül ez SORONKÉNT 3 külön lekérdezést jelentene: 200 projektkódnál
    # 600+ kör, ami a Pénzügyek oldalt másodpercekkel lassította.
    list_options=(
        # A kiadás mellé az EMBERE is kell: a külsős/egyéb bontás részben az ő
        # típusából derül ki (lásd models/project_code.kulsos_koltseg).
        selectinload(ProjectCode.expenses).selectinload(Expense.employee),
        selectinload(ProjectCode.deliverables),
        selectinload(ProjectCode.revenues),
        # A belsős napidíj a forgatások STÁBJÁBÓL jön (lásd
        # services/belsos_koltseg.py), a külsős rész pedig a rájuk szóló
        # TIG-ekből és TIG-tételekből (services/kulsos_koltseg.py) - eager load
        # nélkül ez soronként négy további lekérdezés lenne.
        selectinload(ProjectCode.projects).selectinload(Project.crew),
        selectinload(ProjectCode.projects)
        .selectinload(Project.performance_certificates)
        .selectinload(PerformanceCertificate.tetelek),
        selectinload(ProjectCode.projects)
        .selectinload(Project.tig_tetelek)
        .selectinload(PerformanceCertificateTetel.certificate)
        .selectinload(PerformanceCertificate.tetelek),
    ),
)
