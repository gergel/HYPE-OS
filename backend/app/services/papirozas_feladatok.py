"""A lefutott projektek papírozása FELADATKÉNT.

Amint egy projekt lefutott, másnap fel kell dobni az adminisztrációnak, hogy
készüljenek el hozzá a szerződések és a TIG-ek. A dashboard "Teendőim" widgete
eddig is felhozta a hiányzó papírokat (lásd routes/dashboard.py
_papirozas_tasks), de az csak nézet volt: nem lehetett kipipálni, felosztani,
határidőt írni rá. Ez a modul valódi Task rekordot készít belőle.

Ütemező nincs a rendszerben, ezért az elkészítés IGÉNY SZERINT fut: aki
megnyitja a dashboardot vagy a feladatlistát, azzal együtt "utolérjük" a
lemaradást. Ez azért működik, mert a művelet idempotens - projektenként
legfeljebb egy ilyen feladat születik (lásd tasks.project_id).
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.project import Project
from app.models.task import Task

#: A feladat kategóriája - ez különbözteti meg a kézzel felvett feladatoktól.
KATEGORIA = "Papírozás"

#: Meddig nézünk vissza. A funkció bekapcsolásakor enélkül az összes valaha
#: volt forgatásra születne egy feladat, és használhatatlanná tenné a listát;
#: két hétnél régebbi forgatás papírozását pedig úgyis a hiánylisták
#: (Utókövetés, Belsős TIG) hajtják, nem egy most születő teendő.
VISSZATEKINTES_NAPOK = 14


def _adminisztratorok(db: Session) -> list[Employee]:
    """Kik felelnek a papírozásért - az Adminisztráció szerepkörűek.

    Szerepköre több is lehet valakinek (pl. admin ÉS adminisztráció), ezért a
    továbbiak közt is keresünk (lásd models/employee.szerepkorei). A JSON
    oszlopra nem építünk adatbázis-szintű keresést: kevés emberről van szó, a
    szűrés Pythonban is olcsó, és így nem függünk a JSON-operátorok
    dialektusától."""
    mindenki = db.scalars(select(Employee).where(Employee.is_active.is_(True))).all()
    return [
        e
        for e in mindenki
        if SystemRole.ADMINISZTRACIO in {e.role, *[str(r) for r in (e.tovabbi_szerepkorok or [])]}
    ]


def _feladat_szovege(projekt: Project) -> str:
    nev = projekt.nev or f"Projekt #{projekt.id}"
    return f"Szerződések és TIG-ek készítése – {nev}"


def ensure_papirozas_feladatok(db: Session, ma: date | None = None) -> list[Task]:
    """Létrehozza a hiányzó papírozás-feladatokat, és visszaadja az újakat.

    Egy projekt akkor kap feladatot, ha a forgatása MÁR LEFUTOTT (a forgatás
    napja korábbi, mint a mai) és van külsős stábtagja - akinél nincs senki,
    ott nincs mit szerződni/igazolni. A feladat határideje a forgatás utáni
    nap: "amint lefutott, másnap".

    Idempotens: ha a projekthez már van ilyen feladat, nem készít újat. Ha
    egyetlen adminisztrátor sincs, nem csinál semmit - felelős nélküli
    feladatot nem gyártunk."""
    ma = ma or date.today()
    felelosok = _adminisztratorok(db)
    if not felelosok:
        return []

    hatar = ma - timedelta(days=VISSZATEKINTES_NAPOK)
    projektek = db.scalars(
        select(Project)
        .options(selectinload(Project.crew))
        .where(
            Project.forgatas_datuma.is_not(None),
            Project.forgatas_datuma < ma,
            Project.forgatas_datuma >= hatar,
        )
    ).all()
    if not projektek:
        return []

    mar_van = set(
        db.scalars(
            select(Task.project_id).where(
                Task.kategoria == KATEGORIA,
                Task.project_id.in_([p.id for p in projektek]),
            )
        ).all()
    )

    ujak: list[Task] = []
    for projekt in projektek:
        if projekt.id in mar_van:
            continue
        if not any(e.tipus != EmployeeType.BELSOS for e in projekt.crew):
            continue
        feladat = Task(
            feladat=_feladat_szovege(projekt),
            kategoria=KATEGORIA,
            project_id=projekt.id,
            # "Amint lefutott a projekt, másnap" - a forgatást követő nap.
            hatarido=projekt.forgatas_datuma + timedelta(days=1),
            leiras=(
                "A projekt lefutott. Készüljenek el hozzá az alvállalkozói szerződések és a "
                "teljesítési igazolások (lásd Utókövetés)."
            ),
            felelosok=list(felelosok),
        )
        db.add(feladat)
        ujak.append(feladat)

    if ujak:
        db.commit()
    return ujak
