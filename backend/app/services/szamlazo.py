"""A SZÁMLÁZÓ FÉL feloldása: ki állítja ki a számlát egy stábtag munkájáért.

Ez a modul egy helyen tartja azt a szabályt, amire a szerződés-fázis
(api/routes/subcontractor_contracts.py), a TIG-fázis
(api/routes/performance_certificates.py) és az utókövetés összefoglaló
(api/routes/utokovetes_admin.py) egyaránt épül:

    egy (projekt, stábtag) párhoz tartozó számlázó fél alapból MAGA az ember,
    de a projekten felülírható másik emberre vagy egy vállalkozásra
    (lásd models/project_szamlazo.py).

Amiért érdemes volt kiemelni: a papírok (eseti szerződés, TIG) nem emberenként,
hanem SZÁMLÁZÓ FELENKÉNT készülnek. Ha egy projekten három ember munkáját
ugyanaz a cég számlázza, egyetlen szerződés és egyetlen TIG kell, nem három -
a többiek attól még teljes értékű stábtagok maradnak.

A "kulcs" egy rövid szöveges azonosító ("e12" = 12-es ember, "v3" = 3-as
vállalkozás). Azért szöveg, mert így ugyanaz az útvonal (.../{szamlazo}/save)
tud embert és céget is fogadni, és a puszta szám továbbra is embert jelent -
tehát a korábbi, ember-azonosítós hívások változtatás nélkül működnek."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.models.employee import Employee
from app.models.project import Project
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.vallalkozas import Vallalkozas


@dataclass(frozen=True)
class SzamlazoFel:
    """Egy számlázó fél: pontosan az egyik oldala van kitöltve."""

    employee: Employee | None = None
    vallalkozas: Vallalkozas | None = None

    @property
    def kulcs(self) -> str:
        if self.vallalkozas is not None:
            return f"v{self.vallalkozas.id}"
        assert self.employee is not None
        return f"e{self.employee.id}"

    @property
    def nev(self) -> str:
        if self.vallalkozas is not None:
            return self.vallalkozas.nev
        assert self.employee is not None
        return self.employee.full_name

    @property
    def email(self) -> str | None:
        if self.vallalkozas is not None:
            return self.vallalkozas.email
        assert self.employee is not None
        return self.employee.email

    @property
    def ceg_neve(self) -> str | None:
        if self.vallalkozas is not None:
            return self.vallalkozas.nev
        assert self.employee is not None
        return self.employee.vallakozas_neve or self.employee.full_name

    @property
    def szekhely(self) -> str | None:
        return self.vallalkozas.szekhely if self.vallalkozas else self.employee.vallakozas_szekhely

    @property
    def adoszam(self) -> str | None:
        return self.vallalkozas.adoszam if self.vallalkozas else self.employee.vallalkozas_adoszama

    @property
    def kepviselo(self) -> str | None:
        return self.vallalkozas.kepviselo if self.vallalkozas else self.employee.vallalkozas_kepviselo

    @property
    def nyilvantartasi_szam(self) -> str | None:
        return self.vallalkozas.nyilvantartasi_szam if self.vallalkozas else self.employee.nyilvantartasi_szam

    @property
    def megbizas_targya(self) -> str | None:
        return self.vallalkozas.megbizas_targya if self.vallalkozas else self.employee.megbizas_targya

    @property
    def plusz_afa(self) -> bool | None:
        return self.vallalkozas.plusz_afa if self.vallalkozas else self.employee.plusz_afa


def parse_kulcs(kulcs: str) -> tuple[str, int]:
    """"e12"/"12" -> ("employee", 12), "v3" -> ("vallalkozas", 3).

    A csupasz szám embert jelent: a felület korábban az ember azonosítóját
    tette az útvonalba, és ezek a hívások maradjanak érvényesek."""
    szoveg = (kulcs or "").strip()
    if szoveg.isdigit():
        return "employee", int(szoveg)
    elozo, maradek = szoveg[:1].lower(), szoveg[1:]
    if elozo in {"e", "v"} and maradek.isdigit():
        return ("employee" if elozo == "e" else "vallalkozas"), int(maradek)
    raise ValueError(f"Értelmezhetetlen számlázó azonosító: {kulcs!r}")


def feloldas(db: Session, kulcs: str) -> SzamlazoFel | None:
    """Kulcsból a tényleges fél - None, ha nincs ilyen sor."""
    try:
        fajta, azonosito = parse_kulcs(kulcs)
    except ValueError:
        return None
    if fajta == "employee":
        employee = db.get(Employee, azonosito)
        return SzamlazoFel(employee=employee) if employee is not None else None
    vallalkozas = db.get(Vallalkozas, azonosito)
    return SzamlazoFel(vallalkozas=vallalkozas) if vallalkozas is not None else None


def load_felulirasok(db: Session, project_ids: set[int]) -> dict[tuple[int, int], ProjectSzamlazo]:
    """(projekt, ember) -> felülírás. Egy lekérdezés az egész listanézethez."""
    if not project_ids:
        return {}
    rows = (
        db.query(ProjectSzamlazo)
        .options(selectinload(ProjectSzamlazo.szamlazo_employee), selectinload(ProjectSzamlazo.szamlazo_vallalkozas))
        .filter(ProjectSzamlazo.project_id.in_(project_ids))
        .all()
    )
    return {(r.project_id, r.employee_id): r for r in rows}


def kiadaskent_elszamolt(
    project_id: int, employee_id: int, felulirasok: dict[tuple[int, int], ProjectSzamlazo]
) -> bool:
    """Ez az ember PROJEKT KIADÁSKÉNT van elszámolva ezen a projekten?

    Ha igen, nem kell tőle sem szerződés, sem TIG: nem a munkájáért fizetünk
    neki külön, hanem a díja egy másik tételben (pl. a technika bérleti árában)
    már benne van. Stábtag attól még marad - lásd models/project_szamlazo.py."""
    sor = felulirasok.get((project_id, employee_id))
    return sor is not None and bool(sor.kiadaskent_elszamolva)


def papirt_igenylo_emberek(
    project, emberek: list, felulirasok: dict[tuple[int, int], ProjectSzamlazo]
) -> list:
    """A megadott emberekből azok, akikről egyáltalán kell papír - a kiadásként
    elszámoltak kiesnek."""
    return [e for e in emberek if not kiadaskent_elszamolt(project.id, e.id, felulirasok)]


def szamlazo_fele(
    project: Project, employee: Employee, felulirasok: dict[tuple[int, int], ProjectSzamlazo]
) -> SzamlazoFel:
    """Ki számláz ennek az embernek a munkájáért ezen a projekten?

    Ha a felülírás sora létezik, de a hivatkozott fél időközben törlődött,
    visszaesünk az emberre - egy hiányzó cég ne tüntesse el a papír-teendőt."""
    row = felulirasok.get((project.id, employee.id))
    if row is not None:
        if row.szamlazo_vallalkozas is not None:
            return SzamlazoFel(vallalkozas=row.szamlazo_vallalkozas)
        if row.szamlazo_employee is not None:
            return SzamlazoFel(employee=row.szamlazo_employee)
    return SzamlazoFel(employee=employee)


@dataclass
class SzamlazoCsoport:
    """Egy számlázó fél és az általa lefedett stábtagok EGY projekten.

    A `sajat` azt jelenti, hogy a fél maga is stábtag ezen a projekten (tehát
    a saját munkájáról is szól a papír) - a felületen ezt írjuk ki
    "Ladányi Máté (Balla Berci helyett is)" formában."""

    fel: SzamlazoFel
    tagok: list[Employee]

    @property
    def kulcs(self) -> str:
        return self.fel.kulcs

    @property
    def sajat(self) -> bool:
        emp = self.fel.employee
        return emp is not None and any(t.id == emp.id for t in self.tagok)

    @property
    def helyettesitettek(self) -> list[Employee]:
        """Akiket a fél a SAJÁT munkáján felül fed le."""
        emp = self.fel.employee
        return [t for t in self.tagok if emp is None or t.id != emp.id]

    def cimke(self) -> str:
        if not self.helyettesitettek:
            return self.fel.nev
        nevek = ", ".join(t.full_name for t in self.helyettesitettek)
        return f"{self.fel.nev} ({nevek} helyett is)" if self.sajat else f"{self.fel.nev} ({nevek} munkájáért)"


def csoportok(
    project: Project, emberek: list[Employee], felulirasok: dict[tuple[int, int], ProjectSzamlazo]
) -> list[SzamlazoCsoport]:
    """A projekt megadott stábtagjai számlázó felenként összefogva.

    A sorrend a stáblista sorrendjét követi (az első előfordulás dönt), hogy a
    felületen ne ugráljon a lista két betöltés között."""
    rendezett: dict[str, SzamlazoCsoport] = {}
    for e in emberek:
        fel = szamlazo_fele(project, e, felulirasok)
        csoport = rendezett.get(fel.kulcs)
        if csoport is None:
            csoport = SzamlazoCsoport(fel=fel, tagok=[])
            rendezett[fel.kulcs] = csoport
        csoport.tagok.append(e)
    return list(rendezett.values())
