import os
from datetime import date, datetime, timezone

from fastapi import Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import (
    Role,
    get_current_user,
    hash_password,
    require_page_action,
    require_roles,
    vedett_rendszergazda,
)
from app.models.contract import Contract, ContractType, keretszerzodes_ervenyes, megkotott_keretszerzodes
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.employee_document import EmployeeDocument
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.rate import Rate
from app.models.timesheet import Timesheet
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeDocumentRead,
    EmployeeRead,
    EmployeeUpdate,
    RateCreate,
    RateRead,
    RateUpdate,
)
from app.services import deliverable_actions, document_storage
from app.services.hu_datum import ev_honap_szoveg


def _hash_employee_password(data: dict, db: Session) -> dict:
    password = data.pop("password", None)
    if password:
        data["hashed_password"] = hash_password(password)
    return data


#: Amit a védett rendszergazda fiókján nem lehet elállítani. Az `email` is itt
#: van, mert a védettség A CÍMEN múlik (lásd core/security.vedett_rendszergazda):
#: átírni annyi lenne, mint kikapcsolni a védelmet.
_VEDETT_MEZOK = ("is_active", "role", "tovabbi_szerepkorok", "email", "hashed_password")


def _vedett_fiok_vedelme(obj: Employee, data: dict, _db: Session) -> None:
    """A védett rendszergazda fiókját nem lehet kikapcsolni vagy lefokozni.

    A futásidejű ellenőrzések ugyan átengedik akkor is, ha a rekordban rossz
    érték áll (lásd core/security.py), de attól még ne lehessen elrontani: a
    Beállítások és a Csapat oldal mást mutatna, mint ami igaz, és a következő
    ránéző azt hinné, hogy a fiók tényleg ki van kapcsolva.

    Csak akkor szólunk, ha a beküldött érték TÉNYLEG változtatna - így a
    részletnézet "mentsük az egész űrlapot" jellegű PATCH-e nem akad fenn
    azon, hogy a változatlan szerepkört is elküldi."""
    if not vedett_rendszergazda(obj):
        return
    valtoztat = [
        mezo for mezo in _VEDETT_MEZOK if mezo in data and data[mezo] != getattr(obj, mezo, None)
    ]
    if valtoztat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Ez a védett rendszergazda fiók: a bejelentkezéséhez és a jogosultságához tartozó "
                f"mezői ({', '.join(valtoztat)}) nem módosíthatók. Ha át kell adni, előbb a "
                "VEDETT_ADMIN_EMAILEK beállítást kell átírni."
            ),
        )


def _vedett_fiok_torlese(obj: Employee, _db: Session) -> None:
    if vedett_rendszergazda(obj):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ez a védett rendszergazda fiók: nem törölhető.",
        )


router = build_crud_router(
    model=Employee,
    create_schema=EmployeeCreate,
    update_schema=EmployeeUpdate,
    read_schema=EmployeeRead,
    prefix="/crew",
    tags=["crew"],
    page="/csapat",
    before_create=_hash_employee_password,
    before_update=_vedett_fiok_vedelme,
    before_delete=_vedett_fiok_torlese,
    entity_type="employee",
)


class SetPasswordPayload(BaseModel):
    password: str


@router.post(
    "/{employee_id}/set-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def set_employee_password(employee_id: int, payload: SetPasswordPayload, db: Session = Depends(get_db)):
    """Admin beállítja/visszaállítja egy meglévő munkatárs jelszavát - erre azért
    van szükség, mert a Notionből importált munkatársaknak sosem volt jelszavuk
    (hashed_password=None), tehát bejelentkezéshez valakinek adminként be kell
    állítania egyet nekik (lásd Beállítások oldal, per-felhasználó rész)."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A jelszónak legalább 6 karakter hosszúnak kell lennie")
    employee.hashed_password = hash_password(payload.password)
    db.commit()


class UtomunkaProjektIdo(BaseModel):
    """Egy vágó összesített utómunka-ideje EGY projekten, EGY hónapon belül."""

    project_id: int | None
    project_nev: str | None
    projektkod: str | None
    anyagok_szama: int
    total_minutes: float
    total_cost: float | None = None


class UtomunkaHonapIdo(BaseModel):
    """Egy HÓNAP összesítése: mennyit vágott a munkatárs, mennyibe került, és
    ezen belül projektenként hogyan oszlik meg."""

    ev: int
    honap: int
    honap_szoveg: str
    total_minutes: float
    total_cost: float | None = None
    projektek: list[UtomunkaProjektIdo] = []


class VagottAnyag(BaseModel):
    """Egy anyag, amin ez a vágó VALAHA dolgozott."""

    id: int
    projekt_neve: str
    allapot: str | None = None
    projektkod: str | None = None
    utoljara: datetime | None = None
    osszes_perc: float = 0


@router.get("/{employee_id}/vagott-anyagok", response_model=list[VagottAnyag])
def get_vagott_anyagok(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Minden anyag, amin ennek a munkatársnak VALAHA futott az időmérője -
    a legutóbb érintettel elöl.

    Szándékosan nem a Deliverable.vago_employee_id-t nézzük: az csak azt
    mondja meg, ki a jelenlegi kijelölt vágó. Egy anyagon többen is
    dolgozhattak, és a kijelölés utólag át is kerülhet másra - a tényleges
    munkát a munkaidő-sorok (Timesheet) őrzik."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")

    sorok = (
        db.query(Timesheet, Deliverable, ProjectCode)
        .join(Deliverable, Timesheet.deliverable_id == Deliverable.id)
        .outerjoin(ProjectCode, Deliverable.project_code_id == ProjectCode.id)
        .filter(Timesheet.employee_id == employee_id)
        .all()
    )

    anyagok: dict[int, VagottAnyag] = {}
    for timesheet, deliverable, projektkod in sorok:
        adat = anyagok.get(deliverable.id)
        if adat is None:
            adat = VagottAnyag(
                id=deliverable.id,
                projekt_neve=deliverable.projekt_neve,
                allapot=deliverable.allapot,
                projektkod=projektkod.projektkod if projektkod else None,
            )
            anyagok[deliverable.id] = adat
        adat.osszes_perc += float(timesheet.time_minutes or timesheet.idotartam_perc or 0)
        veg = timesheet.end_date or timesheet.start_date
        if veg is not None and (adat.utoljara is None or veg > adat.utoljara):
            adat.utoljara = veg

    # A legutóbb érintett anyag elöl; akinél nincs időpont, a lista végén.
    return sorted(
        anyagok.values(),
        key=lambda a: (a.utoljara is not None, a.utoljara or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )


@router.get("/{employee_id}/utomunka-ido", response_model=list[UtomunkaHonapIdo])
def get_utomunka_ido(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Mennyit vágott ez a munkatárs HÓNAPOKRA bontva, hónapon belül pedig
    projektenként - a személy adatlapján jelenik meg (lásd
    components/UtomunkaIdoHavonta.tsx). A projekt nélküli anyagok egy közös,
    "Projekt nélkül" sorba kerülnek (project_id=None).

    A hónapot a munka KEZDÉSE (start_date) dönti el. A még futó mérés is
    beleszámít, a mostani állásával - így a felületen látott összeg ugyanaz,
    mint az anyag oldalán ketyegő időmérőé.

    A forintos oszlop csak annak megy vissza, akinek a Pénzügy oldalhoz van
    hozzáférése (ugyanaz a szabály, mint az Utómunka oldalon - lásd
    services/deliverable_actions._may_see_costs)."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")

    rows = (
        db.query(Timesheet, Deliverable, Project)
        .join(Deliverable, Timesheet.deliverable_id == Deliverable.id)
        .outerjoin(Project, Deliverable.project_id == Project.id)
        .filter(Timesheet.employee_id == employee_id, Timesheet.start_date.isnot(None))
        .all()
    )

    lathat_koltseget = deliverable_actions._may_see_costs(db, current_user)
    most = datetime.now(timezone.utc)
    orabere_gyorsito: dict[int, float | None] = {}
    honapok: dict[tuple[int, int], UtomunkaHonapIdo] = {}
    projektek: dict[tuple[int, int], dict[int | None, UtomunkaProjektIdo]] = {}
    anyagok: dict[tuple[int, int, int | None], set[int]] = {}

    for timesheet, deliverable, project in rows:
        if timesheet.end_date is None:
            # Még fut: a mostani állásával számoljuk, hogy ne hiányozzon a
            # havi összesítésből, amíg valaki le nem állítja.
            percek = max(0.0, (most - timesheet.start_date).total_seconds() / 60)
            koltseg = deliverable_actions.szamolt_koltseg(
                percek, deliverable_actions.sor_orabere(db, timesheet, orabere_gyorsito)
            )
        else:
            percek = deliverable_actions.sor_percei(timesheet)
            # Rögzített összeg híján az időből és az órabérből számoljuk -
            # ugyanúgy, mint az anyag oldalán (lásd sor_koltsege), különben az
            # importált méréseknél üres maradna a forintos oszlop.
            koltseg = deliverable_actions.sor_koltsege(db, timesheet, orabere_gyorsito)

        honap_kulcs = (timesheet.start_date.year, timesheet.start_date.month)
        projekt_kulcs = project.id if project is not None else None
        if honap_kulcs not in honapok:
            honapok[honap_kulcs] = UtomunkaHonapIdo(
                ev=honap_kulcs[0],
                honap=honap_kulcs[1],
                honap_szoveg=ev_honap_szoveg(*honap_kulcs),
                total_minutes=0,
                total_cost=0 if lathat_koltseget else None,
            )
            projektek[honap_kulcs] = {}
        if projekt_kulcs not in projektek[honap_kulcs]:
            projektek[honap_kulcs][projekt_kulcs] = UtomunkaProjektIdo(
                project_id=projekt_kulcs,
                project_nev=project.nev if project is not None else None,
                projektkod=project.projektkod_szoveg if project is not None else None,
                anyagok_szama=0,
                total_minutes=0,
                total_cost=0 if lathat_koltseget else None,
            )
            anyagok[(*honap_kulcs, projekt_kulcs)] = set()

        honapok[honap_kulcs].total_minutes += percek
        projektek[honap_kulcs][projekt_kulcs].total_minutes += percek
        if lathat_koltseget and koltseg is not None:
            honapok[honap_kulcs].total_cost = (honapok[honap_kulcs].total_cost or 0) + koltseg
            sor = projektek[honap_kulcs][projekt_kulcs]
            sor.total_cost = (sor.total_cost or 0) + koltseg
        anyagok[(*honap_kulcs, projekt_kulcs)].add(deliverable.id)

    for honap_kulcs, honap in honapok.items():
        for projekt_kulcs, sor in projektek[honap_kulcs].items():
            sor.anyagok_szama = len(anyagok[(*honap_kulcs, projekt_kulcs)])
        honap.projektek = sorted(projektek[honap_kulcs].values(), key=lambda s: s.total_minutes, reverse=True)

    # Legfrissebb hónap elöl - azt nézi meg az ember legelőször.
    return sorted(honapok.values(), key=lambda h: (h.ev, h.honap), reverse=True)


@router.get("/{employee_id}/munkaszerzodesek", response_model=list[EmployeeDocumentRead])
def list_munkaszerzodesek(
    employee_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    return employee.documents


@router.post("/{employee_id}/munkaszerzodesek", response_model=EmployeeDocumentRead)
async def upload_munkaszerzodes(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    """Egy dokumentum (pl. munkaszerződés PDF/Word/kép) feltöltése egy
    munkatárshoz - egy munkatársnak tetszőleges számú fájlja lehet, mindegyik
    saját R2 kulcs alatt (a dokumentum id-ja alapján), egyenként törölhetők."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")
    filename = file.filename or "dokumentum"
    content_type = file.content_type or "application/octet-stream"
    doc = EmployeeDocument(employee_id=employee_id, filename=filename, content_type=content_type, storage_key="", url="")
    db.add(doc)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"munkaszerzodes/{employee_id}/{doc.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    doc.storage_key = key
    doc.url = url
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{employee_id}/munkaszerzodesek/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_munkaszerzodes(
    employee_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/csapat", "edit")),
):
    doc = db.get(EmployeeDocument, document_id)
    if doc is None or doc.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="A dokumentum nem található")
    document_storage.delete_object(doc.storage_key)
    db.delete(doc)
    db.commit()


rates_router = build_crud_router(
    model=Rate,
    create_schema=RateCreate,
    update_schema=RateUpdate,
    read_schema=RateRead,
    prefix="/rates",
    tags=["crew"],
    page="/csapat",
)


# --- Külsős munkatárs: min dolgozott és mennyiért ---------------------------
#
# A külsősöknél nincs havi bérezés (az a belsősök világa): egy külsős egy
# PROJEKTEN vesz részt, arra vagy eseti szerződés készül neki, vagy van álló
# keretszerződése, és a végén a TIG mondja meg, mennyiért csinálta. Ez a
# végpont ezt gyűjti egy helyre a munkatárs adatlapjára: melyik projekten
# vett részt, mennyit fizettünk neki, és hol van a hozzá tartozó papír
# (szerződés, TIG, számla).


class MunkaDokumentum(BaseModel):
    cimke: str
    url: str


class KulsosProjektMunka(BaseModel):
    project_id: int | None = None
    project_nev: str | None = None
    forgatas_datuma: date | None = None
    projektkod: str | None = None
    megbizas_targya: str | None = None
    netto: float | None = None
    brutto: float | None = None
    tig_allapot: str | None = None
    szamla_kifizetve: bool = False
    #: A számla-lépést kihagytuk: nem várunk se számlát, se kifizetést (lásd
    #: routes/performance_certificates.skip_szamla).
    szamla_kihagyva: bool = False
    #: A projekthez tartozó papírok: eseti szerződés (ha nem keretszerződéssel
    #: dolgozik), a TIG dokumentuma és a hozzá feltöltött számlák.
    dokumentumok: list[MunkaDokumentum] = []
    #: Igaz, ha erre a projektre NEM készült külön szerződés, mert a
    #: munkatársnak álló keretszerződése van.
    keretszerzodessel: bool = False


class KulsosMunkakOsszesites(BaseModel):
    projektek: list[KulsosProjektMunka] = []
    osszes_netto: float = 0
    osszes_brutto: float = 0
    #: A munkatárs álló keretszerződése (ha van) - a projekt-soroknál ezért
    #: nincs külön szerződés.
    keretszerzodes_id: int | None = None
    keretszerzodes_url: str | None = None


@router.get("/{employee_id}/munkak", response_model=KulsosMunkakOsszesites)
def kulsos_munkak(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy (jellemzően külsős) munkatárs projektjei: min dolgozott, mennyiért,
    és hol vannak a hozzá tartozó papírok.

    A sorok a TIG-ekből jönnek (az mondja meg, mennyiért csinálta), és mellé
    kerül a projekthez tartozó eseti szerződés is - ha viszont a munkatársnak
    álló KERETSZERZŐDÉSE van, projektenként nincs külön szerződés, ezért azt
    egyszer, a lista fölött mutatjuk."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")

    # Álló keretszerződés - de csak a VALÓDI (lásd models/contract.py
    # megkotott_keretszerzodes): a munkatárs Notion-lapjáról átvett, projekt
    # nélküli sorok eseti megbízási szerződések, nem keretszerződés.
    keretszerzodesek = [
        c
        for c in db.query(Contract)
        .options(selectinload(Contract.idoszakok))
        .filter(
            Contract.employee_id == employee_id,
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.project_id.is_(None),
        )
        .order_by(Contract.id.desc())
        .all()
        if megkotott_keretszerzodes(c)
    ]
    keretszerzodes = keretszerzodesek[0] if keretszerzodesek else None

    esetiek = {
        c.project_id: c
        for c in db.query(Contract)
        .options(selectinload(Contract.project).selectinload(Project.project_code))
        .filter(Contract.employee_id == employee_id, Contract.project_id.is_not(None))
        .order_by(Contract.id)
        .all()
    }

    tigek = (
        db.query(PerformanceCertificate)
        .options(
            selectinload(PerformanceCertificate.invoices),
            selectinload(PerformanceCertificate.project).selectinload(Project.project_code),
        )
        .filter(PerformanceCertificate.employee_id == employee_id)
        .all()
    )

    def projekt_mezok(projekt: Project | None) -> dict:
        return {
            "project_nev": projekt.nev if projekt else None,
            "forgatas_datuma": projekt.forgatas_datuma if projekt else None,
            "projektkod": projekt.project_code.projektkod if projekt and projekt.project_code else None,
        }

    sorok: list[KulsosProjektMunka] = []
    for tig in tigek:
        dokumentumok: list[MunkaDokumentum] = []
        eseti = esetiek.get(tig.project_id)
        if eseti is not None and eseti.szerzodes_file_url:
            dokumentumok.append(MunkaDokumentum(cimke="Szerződés", url=eseti.szerzodes_file_url))
        if tig.file_url:
            dokumentumok.append(MunkaDokumentum(cimke="TIG", url=tig.file_url))
        for szamla in tig.invoices:
            dokumentumok.append(MunkaDokumentum(cimke=f"Számla – {szamla.filename}", url=szamla.url))

        netto = float(tig.netto_osszeg) if tig.netto_osszeg is not None else None
        brutto = round(netto * 1.27, 2) if (netto is not None and tig.plusz_afa) else netto
        sorok.append(
            KulsosProjektMunka(
                project_id=tig.project_id,
                **projekt_mezok(tig.project),
                megbizas_targya=tig.megbizas_targya,
                netto=netto,
                brutto=brutto,
                tig_allapot=tig.allapot,
                szamla_kifizetve=bool(tig.szamla_kifizetve),
                szamla_kihagyva=bool(tig.szamla_kihagyva),
                dokumentumok=dokumentumok,
                # A keretszerződés csak akkor váltja ki az eseti szerződést, ha a
                # FORGATÁS NAPJÁN élt (lásd models/contract.py idoszakok).
                keretszerzodessel=eseti is None
                and any(
                    keretszerzodes_ervenyes(c, (tig.project.forgatas_datuma if tig.project else None) or date.today())
                    for c in keretszerzodesek
                ),
            )
        )

    # Amelyik projektre már van szerződése, de TIG még nincs: az is munka, amin
    # részt vett - csak még nem tudjuk, mennyiért. Ezek nélkül a lista hiányos
    # lenne (a szerződés kiküldése és a TIG között hetek is eltelnek).
    tiges_projektek = {tig.project_id for tig in tigek}
    for project_id, eseti in esetiek.items():
        if project_id in tiges_projektek:
            continue
        netto = float(eseti.netto_osszeg) if eseti.netto_osszeg is not None else None
        sorok.append(
            KulsosProjektMunka(
                project_id=project_id,
                **projekt_mezok(eseti.project),
                megbizas_targya=eseti.megbizas_targya,
                netto=netto,
                brutto=round(netto * 1.27, 2) if (netto is not None and eseti.plusz_afa) else netto,
                tig_allapot=None,
                dokumentumok=(
                    [MunkaDokumentum(cimke="Szerződés", url=eseti.szerzodes_file_url)]
                    if eseti.szerzodes_file_url
                    else []
                ),
            )
        )

    # A legfrissebb forgatás elöl; dátum nélküli sorok a végén.
    sorok.sort(key=lambda s: (s.forgatas_datuma is not None, s.forgatas_datuma or date.min), reverse=True)
    return KulsosMunkakOsszesites(
        projektek=sorok,
        osszes_netto=float(sum(s.netto or 0 for s in sorok)),
        osszes_brutto=float(sum(s.brutto or 0 for s in sorok)),
        keretszerzodes_id=keretszerzodes.id if keretszerzodes else None,
        keretszerzodes_url=keretszerzodes.szerzodes_file_url if keretszerzodes else None,
    )


# --- Miken vett részt: forgatások és vágás -----------------------------------
#
# Minden munkatársnál (belsős és külsős egyaránt) meg kell látszania, hogy
# melyik projekteken dolgozott. Két külön dolog kerül egy listába:
#   - FORGATÁS: rajta van a projekt stáblistáján (project_crew),
#   - VÁGÁS: futott az időmérője a projekthez tartozó valamelyik anyagon.
# A kettő nem ugyanaz - van, aki csak vág, és van, aki csak forgat -, ezért
# soronként jelezzük, melyikről van szó (és ha vágott, mennyit).


class ReszvetelSor(BaseModel):
    project_id: int
    project_nev: str | None = None
    forgatas_datuma: date | None = None
    projektkod: str | None = None
    allapot: str | None = None
    #: Rajta volt a stáblistán (forgatáson vett részt).
    stabtag: bool = False
    #: Dolgozott a projekt valamelyik anyagán (vágás).
    vagott: bool = False
    #: Vágással töltött idő ezen a projekten, percben (csak ha vágott).
    vagas_percek: float = 0
    #: Hány anyagon dolgozott ezen a projekten.
    anyagok_szama: int = 0


@router.get("/{employee_id}/reszvetel", response_model=list[ReszvetelSor])
def get_reszvetel(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Melyik projekteken vett részt ez a munkatárs - forgatáson, vágáson vagy
    mindkettőn. A legfrissebb forgatás elöl, a dátum nélküliek a végén."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Munkatárs nem található")

    sorok: dict[int, ReszvetelSor] = {}

    def sor(projekt: Project) -> ReszvetelSor:
        meglevo = sorok.get(projekt.id)
        if meglevo is None:
            meglevo = ReszvetelSor(
                project_id=projekt.id,
                project_nev=projekt.nev,
                forgatas_datuma=projekt.forgatas_datuma,
                projektkod=projekt.project_code.projektkod if projekt.project_code else None,
                allapot=projekt.allapot,
            )
            sorok[projekt.id] = meglevo
        return meglevo

    # 1) Forgatások: ahol rajta van a stáblistán.
    stabos = (
        db.query(Project)
        .options(selectinload(Project.project_code))
        .filter(Project.crew.any(Employee.id == employee_id))
        .all()
    )
    for projekt in stabos:
        sor(projekt).stabtag = True

    # 2) Vágás: ahol futott az időmérője a projekt valamelyik anyagán. Nem a
    # Deliverable.vago_employee_id-t nézzük (az csak a KIJELÖLT vágó), hanem a
    # tényleges munkaidő-sorokat - ugyanaz az elv, mint a vágott anyagoknál.
    meresek = (
        db.query(Timesheet, Deliverable, Project)
        .join(Deliverable, Timesheet.deliverable_id == Deliverable.id)
        .join(Project, Deliverable.project_id == Project.id)
        .options(selectinload(Project.project_code))
        .filter(Timesheet.employee_id == employee_id)
        .all()
    )
    anyagok: dict[int, set[int]] = {}
    for timesheet, deliverable, projekt in meresek:
        adat = sor(projekt)
        adat.vagott = True
        adat.vagas_percek += float(timesheet.time_minutes or timesheet.idotartam_perc or 0)
        anyagok.setdefault(projekt.id, set()).add(deliverable.id)
    for project_id, halmaz in anyagok.items():
        sorok[project_id].anyagok_szama = len(halmaz)

    return sorted(
        sorok.values(),
        key=lambda s: (s.forgatas_datuma is not None, s.forgatas_datuma or date.min),
        reverse=True,
    )
