from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.employee import Employee, SystemRole as Role, van_szerepkore
from app.models.user_access import PageAccessConfig

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen vagy lejárt token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Employee:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Érvénytelen token")
    user = db.get(Employee, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Felhasználó nem található")
    return user


def vedett_admin_emailek() -> set[str]:
    """A védett rendszergazda címek, kisbetűsítve (lásd settings)."""
    return {cim.strip().casefold() for cim in settings.vedett_admin_emailek.split(",") if cim.strip()}


def vedett_rendszergazda(employee: Employee | None) -> bool:
    """VÉDETT RENDSZERGAZDA-e ez a fiók?

    Ez a fiók sosem eshet ki a rendszerből: mindig aktív, mindig admin, és
    sosem korlátozza oldal- vagy mező-jogosultság. A jogosultságokat ugyanazon
    a felületen állítjuk, amit azok védenek, tehát egyetlen félrekattintás
    (inaktívra állítás, szerepkör átírása, "hozzáférés visszavonása") ki tudja
    zárni azt az embert, aki egyedül tudná visszaadni a jogot - adatbázis
    nélkül pedig kívülről nem javítható.

    A cím alapján dől el, nem azonosító alapján: a rekord törölhető és újra
    felvehető, importálás után más id-t kaphat, a cím viszont ugyanaz marad.

    FONTOS: az e-mail cím a rendszerben NEM egyedi (lásd models/employee.py),
    tehát ha valaki más rekordjába ugyanez a cím kerül, az a fiók is védetté
    válna. Ez tudatos csere: a bezárkózás kockázata nagyobb, mint egy közös
    postafiók-címé, és a belépéshez a jelszó úgyis kell. Ezért viszont a
    védett címre csak SAJÁT, személyes címet adj meg, közös postafiókot ne."""
    if employee is None or not employee.email:
        return False
    return employee.email.strip().casefold() in vedett_admin_emailek()


#: Kik írhatnak alapértelmezetten (a page_permissions ezt tovább szűkítheti,
#: de sosem bővítheti). Az Adminisztráció szerepkör azért van itt, mert épp az
#: a dolga, hogy a papírokat (TIG-ek, szerződések) elkészítse - olvasási joggal
#: a szerepkör értelmetlen lenne.
DEFAULT_WRITE_ROLES: tuple[Role, ...] = (Role.ADMIN, Role.OPERATOR, Role.ADMINISZTRACIO)


def require_roles(*roles: Role):
    def dependency(current_user: Employee = Depends(get_current_user)) -> Employee:
        # A védett rendszergazda minden szerepkört visel: ha az adatbázisban
        # valahogy mégis átíródott a szerepköre, attól még nem zárható ki.
        if vedett_rendszergazda(current_user):
            return current_user
        # A TELJES szerepkör-halmazt nézzük, nem csak az elsődlegest: egy
        # embernek több szerepköre is lehet (lásd models/employee.szerepkorei).
        if not van_szerepkore(current_user, *roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nincs jogosultságod ehhez a művelethez",
            )
        return current_user

    return dependency


#: A PROJEKTHEZ RENDELT ESZKÖZÖK (Assignment) saját jogosultsági kulcsa.
#:
#: Nem valódi oldal (nincs ilyen menüpont, admin sem tudja beállítani):
#: kizárólag az alábbi aliaszokon át kapható meg. Azért kell külön kulcs, mert
#: a technika felvezetése a PROJEKTEN történik, a /felszereles oldal
#: create/delete joga viszont magukat az ESZKÖZÖKET (leltári tételeket) is
#: engedné létrehozni/törölni - a kettőt nem szabad összekötni.
FOGLALAS_OLDAL = "/felszereles/foglalas"

#: OLDAL-ALIASZOK: melyik MÁSIK oldal joga ér fel ezzel, és mely műveletekre.
#:
#: Felépítés: cél oldal -> forrás oldal -> {forrás művelet: átadott műveletek}.
#: Az aliaszok NEM láncolódnak: mindig a nyersen beállított jogokat nézzük,
#: tehát ha egy jog két lépésen át járna, azt külön sorként kell felvenni.
#:
#: 1) A DISZPÓ (naptár) joga a PROJEKT oldalt is megnyitja - nézésre és
#:    szerkesztésre. Aki a diszpókat viszi, annak a projekten van dolga: látnia
#:    kell a gyártás és a technika adatait, írnia a gyártás kommentet,
#:    feltöltenie a diszpó levél mellékleteit, és kiküldenie az előzetes és a
#:    teljes diszpót. Enélkül a "csak diszpó" hozzáférés használhatatlan volt: a
#:    felület beengedte a naptárba, de a projekt megnyitásakor 403 jött.
#:    LÉTREHOZNI és TÖRÖLNI viszont nem tud projektet: az nem a diszpós dolga.
#:
#: 2) A projekt SZERKESZTÉSE magában foglalja a technika felvezetését is: a
#:    projekt technika blokkjában az eszköz hozzáadása/levétele MAGA a
#:    szerkesztés, nincs mit "edit"-elni rajta. Ezért itt az "edit" tudatosan
#:    create/delete jogot ad - de csak a FOGLALÁSRA, magára a leltárra nem.
#:    A /felszereles oldal joga változatlanul viszi tovább a sajátját, hogy a
#:    korábbi beállítások ugyanúgy működjenek.
#:
#: 3) Aki a projekten technikát vezet fel, annak a FELSZERELÉS oldalt is látnia
#:    kell: onnan tudja megnézni, mi van a leltárban, mit is jelent egy tétel, és
#:    a projekten felvett eszközök nevei is oda hivatkoznak. Ez NÉZÉS: a leltárat
#:    bővíteni, javítani, törölni és leltározni továbbra is csak a /felszereles
#:    saját jogával lehet.
OLDAL_ALIASZOK: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {
    "/projektek": {
        "/naptar": {"view": ("view",), "edit": ("edit",)},
    },
    "/felszereles": {
        "/projektek": {"view": ("view",)},
        "/naptar": {"view": ("view",)},
    },
    FOGLALAS_OLDAL: {
        "/felszereles": {"view": ("view",), "create": ("create",), "delete": ("delete",)},
        "/projektek": {"view": ("view",), "edit": ("view", "create", "delete")},
        "/naptar": {"view": ("view",), "edit": ("view", "create", "delete")},
    },
}

#: Amik nem valódi oldalak: sosem kerülnek a menübe és a navigáció-zárba.
VIRTUALIS_OLDALAK: frozenset[str] = frozenset({FOGLALAS_OLDAL})


def _oldal_muveletei(page_permissions: dict[str, list[str]], page: str) -> set[str] | None:
    """Mit tehet ezen az oldalon - az aliaszokkal együtt.

    None: az oldal egyáltalán nem engedélyezett (se magában, se aliaszon át).
    Üres halmaz nem fordul elő: ha az oldal kulcsa ott van, a "view" jár."""
    sajat = page_permissions.get(page)
    engedve: set[str] = set(sajat) | {"view"} if sajat is not None else set()

    for alias, atkotes in OLDAL_ALIASZOK.get(page, {}).items():
        alias_muveletek = page_permissions.get(alias)
        if alias_muveletek is None:
            continue
        # Ha az oldal kulcsa ott van, a "view" jár rá - ugyanaz a szabály,
        # mint fent a sajátnál (lásd models/user_access.py).
        van = set(alias_muveletek) | {"view"}
        for forras, atadott in atkotes.items():
            if forras in van:
                engedve |= set(atadott)

    return engedve or None


def elerheto_oldalak(page_permissions: dict[str, list[str]] | None) -> list[str] | None:
    """Mely oldalak érhetők el - a beállítottak ÉS az aliaszon át kapottak.

    Ebből épül az oldalsáv és ezt nézi a navigáció-zár (lásd
    routes/user_access.get_my_access "allowed_pages"). Az aliaszolt oldalaknak
    is meg KELL jelenniük: a diszpós a projekt technika blokkjából a
    Felszerelés oldalra hivatkozik, és értelmetlen lenne olyan oldalra
    beengedni, ahova a menü el sem viszi.

    None: nincs korlátozás (mindent lát)."""
    if page_permissions is None:
        return None
    oldalak = list(page_permissions.keys())
    for oldal in OLDAL_ALIASZOK:
        if oldal in VIRTUALIS_OLDALAK or oldal in page_permissions:
            continue
        if _oldal_muveletei(page_permissions, oldal) is not None:
            oldalak.append(oldal)
    return oldalak


def check_page_action(db: Session, employee: Employee, page: str, action: str) -> None:
    """A durvább admin/operator szerepkör-ellenőrzés (lásd require_roles) UTÁN
    hívva a finomabb, oldal+művelet-szintű írási jogosultságot ellenőrzi - ha
    az alkalmazottnak van PageAccessConfig sora ÉS abban page_permissions be
    van állítva, csak azokon az oldalakon/műveleteken enged, amiket admin
    kifejezetten megadott neki (lásd Beállítások oldal). Ha nincs sora, vagy a
    page_permissions None, korlátozás nélkül enged (ugyanaz az alapértelmezett
    viselkedés, mint az oldal-láthatóságnál).

    A védett rendszergazdát semmilyen beállítás nem korlátozza: ha valakinél
    elrontanak egy jogosultságot, ő az egyetlen biztos kiút."""
    if vedett_rendszergazda(employee):
        return
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
    if config is None or config.page_permissions is None:
        return
    allowed = _oldal_muveletei(config.page_permissions, page)
    if allowed is None or action not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nincs jogosultságod ehhez a művelethez ezen az oldalon.",
        )


def check_tab_action(db: Session, employee: Employee, page: str, tab_key: str, action: str) -> None:
    """A részletnézet-fülek (lásd models/detail_tab.py) szintjén finomítja a
    check_page_action-t: a "{page}:{tab_key}" összetett kulcs csak akkor
    SZŰKÍTI a jogosultságot, ha admin kifejezetten beállította azt a
    munkatársnak (lásd Beállítások oldal, UserAccessManager fülenkénti
    Látja/Szerkesztheti checkboxai) - ha nincs ilyen összetett kulcs a
    page_permissions dict-ben, az adott fül a MEGLÉVŐ, oldal-szintű jogot
    örökli (nem esik vissza tiltásra). Enélkül minden olyan munkatárs, akinek
    admin BÁRMELYIK oldalhoz korlátozást állított be (page_permissions nem
    None), az ÖSSZES részletnézet-fülön elveszítené a hozzáférést minden
    olyan fülhöz, amihez admin még nem konfigurált explicit fül-szintű
    engedélyt - beleértve a bespoke widgeteket (pl. eszközfoglalás, szerződés
    készítés) is, amik nem is mező-szerkesztést jelentenek, hanem önálló
    akció-gombok egy adott fülön belül.

    A védett rendszergazdára ez sem vonatkozik (lásd vedett_rendszergazda)."""
    if vedett_rendszergazda(employee):
        return
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
    if config is None or config.page_permissions is None:
        return
    fulre_szabott = config.page_permissions.get(f"{page}:{tab_key}")
    # A fül-szintű beállítás csak SZŰKÍT: ha nincs ilyen kulcs, az oldal
    # (aliaszokkal együtt számolt) joga öröklődik - lásd _oldal_muveletei.
    allowed = set(fulre_szabott) if fulre_szabott is not None else _oldal_muveletei(config.page_permissions, page)
    if allowed is None or action not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nincs jogosultságod ehhez a művelethez ezen a fülön.",
        )


def require_page_action(page: str, action: str, *write_roles: Role):
    """Standalone (nem build_crud_router-en keresztül regisztrált) végpontokhoz
    - pl. equipment.py Assignment create/delete - ugyanazt az oldal+művelet-
    szintű ellenőrzést adja, mint amit a build_crud_router minden generikus
    create/update/delete végpontja automatikusan megkap."""
    write_roles = write_roles or DEFAULT_WRITE_ROLES
    role_dependency = require_roles(*write_roles)

    def dependency(current_user: Employee = Depends(role_dependency), db: Session = Depends(get_db)) -> Employee:
        check_page_action(db, current_user, page, action)
        return current_user

    return dependency


def lathato_anyagok(db: Session, employee: Employee) -> set[int] | None:
    """Mely utómunka-anyagokat láthatja ez a munkatárs - None, ha mindet.

    A külsős vágóknak adható olyan fiók, amivel EGYETLEN anyagot látnak: azon
    tudják indítani/leállítani az időmérőt és látják a feladatukat, de a többi
    projektünkbe nem látnak bele (lásd models/user_access.py
    lathato_deliverable_idk). Ez a szűkítés a listára és az egyes anyagok
    minden műveletére is vonatkozik.

    Az ADMIN mindig mindent lát: enélkül egy elrontott beállítással saját
    magát is ki lehetne zárni a rendszerből."""
    if van_szerepkore(employee, Role.ADMIN):
        return None
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
    if config is None or config.lathato_deliverable_idk is None:
        return None
    return {int(i) for i in config.lathato_deliverable_idk}


def ellenorizd_anyag_hozzaferest(db: Session, employee: Employee, deliverable_id: int) -> None:
    """404-et dob, ha ez a munkatárs nem láthatja ezt az anyagot.

    Szándékosan 404 és nem 403: egy korlátozott fióknak az sem információ,
    hogy létezik-e a kért anyag."""
    engedett = lathato_anyagok(db, employee)
    if engedett is not None and deliverable_id not in engedett:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utómunka nem található")
