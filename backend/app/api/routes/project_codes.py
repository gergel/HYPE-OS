from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, get_current_user, lathatja_e_az_oldalt, require_page_action
from app.models.contract import Contract
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_code_comment import ProjectCodeComment
from app.schemas.project_code import (
    ProjectCodeCommentCreate,
    ProjectCodeCommentRead,
    ProjectCodeCreate,
    ProjectCodeListRead,
    ProjectCodeRead,
    ProjectCodeUpdate,
)
from app.services import notifications
from app.services import penznem as penznem_szolg
from app.services import projektkod_bontas



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


def _penznem_ellenorzese(obj: ProjectCode, data: dict, _db: Session) -> None:
    """Devizás vállalási árhoz KÖTELEZŐ az árfolyam.

    Enélkül a beírt szám nem értelmezhető: az "1500" lehet 1 500 Ft és 592 500
    Ft is - és a bevétel abból a számból keletkezik. A PATCH tipikusan csak a
    változó mezőt küldi, ezért a beküldött értéket és a rekord mostani
    állapotát EGYÜTT nézzük (lásd _papir_kapcsolok_ellenorzese)."""
    if "penznem" not in data and "arfolyam" not in data:
        return
    penznem = data.get("penznem", obj.penznem)
    arfolyam = data.get("arfolyam", obj.arfolyam)
    try:
        penznem_szolg.ellenorizd(penznem, arfolyam)
    except penznem_szolg.PenznemHiba as hiba:
        raise HTTPException(status_code=400, detail=str(hiba)) from hiba


def _projektkod_ellenorzese(obj: ProjectCode, data: dict, db: Session, _current_user: Employee) -> None:
    """A projektkód PATCH-ének összes együtt-értelmesség ellenőrzése."""
    _papir_kapcsolok_ellenorzese(obj, data, db)
    _penznem_ellenorzese(obj, data, db)


class ProjectCodeOption(BaseModel):
    """Egy projektkód ANNYIRA, amennyi egy címkéhez/választóhoz kell."""

    id: int
    projektkod: str
    project_nev: str | None = None
    client_id: int | None = None
    esemeny_allapota: str | None = None

    model_config = {"from_attributes": True}


#: Külön router, mert a "/valaszthato" útvonalat a CRUD-generátor
#: "/{item_id}" mintája elnyelné - ezt a listát ELŐBB kell bejegyezni
#: (lásd api/routes/__init__.py).
valaszthato_router = APIRouter(prefix="/project-codes", tags=["project-codes"])


@valaszthato_router.get("/valaszthato", response_model=list[ProjectCodeOption])
def list_valaszthato(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A projektkódok CSAK a nevükkel - választóhoz és címke-feloldáshoz.

    Miért külön végpont? Mert a teljes lista minden kódra kiszámolja a
    költségeket, a profitot és a papír-állást: végigjárja a forgatásokat, a
    stábot, az utómunkákat, a méréseket, a kiadásokat és a TIG-eket. 800
    kódnál ez több másodperc és fél megabájt - miközben a Projektek, a
    Naptár, a Pénzügyek, a Dashboard és a munkatárs-adatlap mindebből
    egyetlen dolgot használ: melyik id melyik kódot jelenti.

    Ez a végpont sima oszlopokat olvas, egyetlen lekérdezéssel."""
    sorok = db.execute(
        select(
            ProjectCode.id,
            ProjectCode.projektkod,
            ProjectCode.project_nev,
            ProjectCode.client_id,
            ProjectCode.esemeny_allapota,
        ).order_by(ProjectCode.projektkod)
    ).all()
    return [
        ProjectCodeOption(
            id=sor.id,
            projektkod=sor.projektkod,
            project_nev=sor.project_nev,
            client_id=sor.client_id,
            esemeny_allapota=sor.esemeny_allapota,
        )
        for sor in sorok
    ]


#: A durva admin/operator szerepkör-kapu itt nem érvényes: aki a
#: Beállításokban szerkesztői jogot kapott a Project Code oldalra, az írhatja
#: a projektkód mezőit (pl. a "Mennyiért vállaltuk" összegét) - a szerepköre
#: nem szűkíti tovább. Ugyanaz az elv, mint az Utómunkánál és a
#: diszpó-táblánál (lásd routes/postproduction.py _MINDEN_SZEREPKOR).
_MINDEN_SZEREPKOR = tuple(Role)

#: A projektkód PÉNZ-mezői: aki nem látja a Pénzügyek oldalt, ezekből semmit
#: nem kaphat (a felhasználó kérése) - a felület el is rejti a pénz-blokkokat,
#: ez itt a szerveroldali biztosíték. A számok nullára, a többi üresre megy,
#: hogy a válasz alakja ne változzon (a frontend típusai számot várnak).
_PENZ_MEZOK_NULLA = (
    "bevetel",
    "osszes_koltseg",
    "becsult_profit",
    "kulsos_koltseg",
    "egyeb_kiadas",
    "vagas_koltseg",
    "belsos_munka_koltseg",
)
_PENZ_MEZOK_URES = (
    "bevetel_deviza",
    "hatarido_allas",
    "vallalasi_ar_magyarazat",
    "netto_osszeg",
    "szerzodes_netto_osszeg",
    "fizetesi_hatarido",
    "plusz_afa",
    "szerzodes_plusz_afa",
    "arfolyam",
    # A Notionből örökölt pénz-mezők - a részletnézet mezőrácsában jelennének
    # meg, ezért ezeket is ki kell takarni.
    "profit_szazalek_notion",
    "gyartasi_koltseg_notion",
    "osszes_koltseg_notion",
    "osszesen_netto_notion",
    "netto_notion",
    "brutto_notion",
    "alvallalkozok_koltsege_notion",
    "vagasi_koltseg_notion",
    "forintban_notion",
    "belsos_koltseg_akkor",
    "vallalasi_ar_notion",
    "belsos_koltseg_notion",
    "belso_plusz_koltseg_notion",
    "megerte_e",
)


def _penz_kimenet_szuro(sorok: list[dict], db: Session, user: Employee) -> list[dict]:
    """Pénzügy-hozzáférés nélkül a projektkód pénz-mezői kitakarva mennek ki -
    a jogot EGYSZER kérdezzük le, nem soronként (lásd crud_router
    kimenet_szuro)."""
    if lathatja_e_az_oldalt(db, user, "/penzugyek"):
        return sorok
    for sor in sorok:
        for mezo in _PENZ_MEZOK_NULLA:
            if mezo in sor:
                sor[mezo] = 0
        for mezo in _PENZ_MEZOK_URES:
            if mezo in sor:
                sor[mezo] = None
        if "szamla_hataridok" in sor:
            sor["szamla_hataridok"] = []
    return sorok


router = build_crud_router(
    model=ProjectCode,
    create_schema=ProjectCodeCreate,
    update_schema=ProjectCodeUpdate,
    read_schema=ProjectCodeRead,
    # A lista csak a ténylegesen megjelenített mezőket viszi (lásd
    # schemas/project_code.ProjectCodeListRead) - a Notionből örökölt ~80 extra
    # mező 800 kódnál másfél megabájtnyi fölösleges adat volt minden
    # oldalbetöltésnél.
    list_read_schema=ProjectCodeListRead,
    prefix="/project-codes",
    tags=["project-codes"],
    # Külön jogosultsági hatókör, NEM ugyanaz, mint a Projekteké (lásd
    # projects.py page="/projektek") - a felhasználó explicit kérése, hogy
    # a Project Code-okhoz csak külön, kifejezett jogosultsággal lehessen
    # hozzáférni, ne automatikusan a Projektek jogosultsággal együtt.
    page="/projektek/project-kodok",
    write_roles=_MINDEN_SZEREPKOR,
    entity_type="projectCode",
    before_update=_projektkod_ellenorzese,
    # A ProjectCodeRead számított mezői (osszes_koltseg, becsult_profit)
    # végigjárják a kiadásokat, az utómunkákat és a bevételeket. Eager load
    # nélkül ez SORONKÉNT 3 külön lekérdezést jelentene: 200 projektkódnál
    # 600+ kör, ami a Pénzügyek oldalt másodpercekkel lassította.
    list_options=(
        # A kiadás mellé az EMBERE is kell: a külsős/egyéb bontás részben az ő
        # típusából derül ki (lásd models/project_code.kulsos_koltseg).
        selectinload(ProjectCode.expenses).selectinload(Expense.employee),
        # A vágás ára a MÉRT munkaidőből jön (lásd
        # models/project_code.vagas_koltseg), ezért a mérések is kellenek -
        # enélkül soronként külön lekérdezés indulna értük.
        selectinload(ProjectCode.deliverables).selectinload(Deliverable.timesheets),
        selectinload(ProjectCode.projects).selectinload(Project.deliverables).selectinload(Deliverable.timesheets),
        selectinload(ProjectCode.revenues),
        # A belsős napidíj a forgatások STÁBJÁBÓL jön (lásd
        # services/belsos_koltseg.py), a külsős rész pedig a rájuk szóló
        # TIG-ekből és TIG-tételekből (services/kulsos_koltseg.py) - eager load
        # nélkül ez soronként négy további lekérdezés lenne.
        # A stáb mellé a BELSŐS IDŐSZAKOK is kellenek: a napidíj azt nézi, ki
        # volt AZON A NAPON belsős (lásd services/belsos_idoszak.belsos_a_napon).
        # Enélkül stábtagonként külön lekérdezés indulna értük.
        selectinload(ProjectCode.projects)
        .selectinload(Project.crew)
        .selectinload(Employee.belsos_idoszakok),
        selectinload(ProjectCode.projects)
        .selectinload(Project.performance_certificates)
        .selectinload(PerformanceCertificate.tetelek),
        selectinload(ProjectCode.projects)
        .selectinload(Project.tig_tetelek)
        .selectinload(PerformanceCertificateTetel.certificate)
        .selectinload(PerformanceCertificate.tetelek),
        # A papír-állás jelzői (szerzodes_kesz / tig_kesz) a megrendelői
        # papírokból jönnek, a keret-fedés pedig a projektkódra KÖTÖTT
        # keretszerződés érvényességi időszakaiból - lásd
        # models/project_code.keret_fedi. (Az ügyfél összes szerződését
        # emiatt már nem kell behozni: a kötés a kódon van.)
        selectinload(ProjectCode.megrendeloi_szerzodesek),
        selectinload(ProjectCode.megrendeloi_tigek),
        selectinload(ProjectCode.contract).selectinload(Contract.idoszakok),
    ),
    # Pénzügy-hozzáférés nélkül a pénz-mezők kitakarva mennek ki (a
    # felhasználó kérése) - lásd _penz_kimenet_szuro.
    kimenet_szuro=_penz_kimenet_szuro,
)


class BontasProjekt(BaseModel):
    """Egy forgatás a projektkód alatt, a rá eső költségekkel."""

    id: int
    nev: str | None = None
    forgatas_datuma: date | None = None
    kulsos_koltseg: float
    belsos_koltseg: float
    vagas_koltseg: float
    osszesen: float


class BontasUtomunka(BaseModel):
    """Egy vágandó anyag: mennyi ideig vágtuk és mennyibe került."""

    id: int
    nev: str | None = None
    project_id: int | None = None
    vago_nev: str | None = None
    percek: float
    koltseg: float


class BontasKiadas(BaseModel):
    """Egy kiadás-sor (bérlés, utazás, kellék, TIG-en kívüli külsős díj…)."""

    id: int
    megnevezes: str | None = None
    kinek: str | None = None
    datum: date | None = None
    netto: float | None = None
    osszeg: float
    kifizetve: bool
    #: Melyik fejléc-részbe számít: "kulsos" (TIG-en kívüli külsős kifizetés)
    #: vagy "egyeb" (minden más).
    resz: str


class ProjektkodBontas(BaseModel):
    projektek: list[BontasProjekt]
    utomunkak: list[BontasUtomunka]
    kiadasok: list[BontasKiadas]


@router.get("/{project_code_id}/bontas", response_model=ProjektkodBontas)
def get_bontas(
    project_code_id: int,
    db: Session = Depends(get_db),
    # A durva szerepkör-kapu itt sem érvényes (lásd _MINDEN_SZEREPKOR): a
    # tényleges kapu a lenti Pénzügy-hozzáférés ellenőrzés + az oldal-jog.
    _user: Employee = Depends(require_page_action("/projektek/project-kodok", "view", *_MINDEN_SZEREPKOR)),
):
    """A projektkód költségeinek TÉTELES bontása: forgatásonként, anyagonként
    és egyéb kiadásonként.

    A fejlécben álló négy összeg (külsős, egyéb, vágás, belsős) megmondja,
    mennyi ment el - ez a végpont azt, hogy MIRE. A számok ugyanabból a
    forrásból jönnek, mint az összesítés (lásd services/projektkod_bontas.py),
    tehát a tételek összege a fejléc-számot adja ki."""
    # A tételes bontás színtiszta pénz-adat: Pénzügy-hozzáférés nélkül nem
    # kérhető le (a felület nem is mutatja - lásd project-kodok/[id] oldal).
    if not lathatja_e_az_oldalt(db, _user, "/penzugyek"):
        raise HTTPException(status_code=403, detail="A költségbontáshoz Pénzügyek-hozzáférés kell.")
    kod = db.get(ProjectCode, project_code_id)
    if kod is None:
        raise HTTPException(status_code=404, detail="A projektkód nem található.")
    return ProjektkodBontas(
        projektek=[BontasProjekt(**sor) for sor in projektkod_bontas.projekt_sorok(db, kod)],
        utomunkak=[BontasUtomunka(**sor) for sor in projektkod_bontas.utomunka_sorok(db, kod)],
        kiadasok=[BontasKiadas(**sor) for sor in projektkod_bontas.kiadas_sorok(kod)],
    )


def _comment_read(comment: ProjectCodeComment) -> ProjectCodeCommentRead:
    return ProjectCodeCommentRead(
        id=comment.id,
        project_code_id=comment.project_code_id,
        employee_id=comment.employee_id,
        employee_name=comment.employee.full_name,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.get("/{project_code_id}/comments", response_model=list[ProjectCodeCommentRead])
def get_comments(
    project_code_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/projektek/project-kodok", "view")),
):
    """Egy Project Code hozzászólásai - ugyanaz a chat-szerű minta, mint az
    Utómunkánál (lásd routes/postproduction.py get_comments)."""
    if db.get(ProjectCode, project_code_id) is None:
        raise HTTPException(status_code=404, detail="A projektkód nem található.")
    rows = db.scalars(
        select(ProjectCodeComment)
        .where(ProjectCodeComment.project_code_id == project_code_id)
        .order_by(ProjectCodeComment.created_at)
    ).all()
    return [_comment_read(c) for c in rows]


@router.post("/{project_code_id}/comments", response_model=ProjectCodeCommentRead, status_code=201)
def post_comment(
    project_code_id: int,
    payload: ProjectCodeCommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action("/projektek/project-kodok", "view")),
):
    kod = db.get(ProjectCode, project_code_id)
    if kod is None:
        raise HTTPException(status_code=404, detail="A projektkód nem található.")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="A hozzászólás nem lehet üres.")

    comment = ProjectCodeComment(project_code_id=project_code_id, employee_id=current_user.id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # @Név említésnél értesítést kap a megemlített - ugyanaz a minta, mint az
    # Utómunka hozzászólásainál (lásd services/deliverable_actions.add_comment).
    # A Project Code-nak nincs "felelőse" mezője, tehát nincs automatikus
    # értesítettje - csak a kifejezett említés szól valakinek.
    title = kod.projektkod or f"Project Code #{kod.id}"
    for employee_id in notifications.extract_mentioned_employee_ids(body, db):
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="mention",
            message=f"{current_user.full_name} megemlített egy hozzászólásban: {title}",
            link=f"/projektek/project-kodok/{kod.id}",
            actor_id=current_user.id,
        )
    db.commit()

    return _comment_read(comment)
