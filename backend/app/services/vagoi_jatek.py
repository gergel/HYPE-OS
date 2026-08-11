"""A vágói játék pontszámítása.

A pont KÉT forrásból jön, és a kettőt szándékosan máshogy kezeljük:

- **Ellenőrzésbe tett anyag (50 pont)**: saját esemény-táblából, mert a pont a
  megtörtént eseményhez tartozik, nem az anyag mai állapotához (lásd
  models/vagoi_jatek.py).
- **Vágás (3 perc = 1 pont)**: a timesheet-ekből SZÁMÍTVA, mert ott az adat
  már megvan és folyamatosan keletkezik. Nem másoljuk át egy pont-táblába:
  egy javított időmérés így magától javítja a pontot is, nem kell
  szinkronban tartani két igazságot.

A végén jön az arányosítás munkanapra - ez teszi összemérhetővé azt, aki 12
napot dolgozott, azzal, aki 22-t.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.timesheet import Timesheet
from app.models.vagoi_jatek import (
    ALAP_MUNKANAP,
    ELLENORZES_PONT,
    PERC_PER_PONT,
    VagoEllenorzesEsemeny,
    VagoJatekHonap,
    VagoJatekNap,
)


def _ekezet_nelkul(szoveg: str) -> str:
    """Kisbetűs, ékezet nélküli alak - az állapotnevek szabad szövegek, és
    "Ellenőrzés" / "ellenorzes" / "ELLENŐRZÉSRE VÁR" mind ugyanaz."""
    return "".join(
        c for c in unicodedata.normalize("NFD", szoveg.casefold()) if unicodedata.category(c) != "Mn"
    )


def ellenorzes_allapot(allapot: str | None) -> bool:
    """Ellenőrzésnek számít-e ez az állapot?

    Az állapotok szabad szövegek (admin szerkeszti őket, lásd
    models/deliverable_status.py), ezért nem egy fix listához hasonlítunk,
    hanem a nevében keressük az "ellenőrzés" szót. Így egy átnevezés
    ("Ellenőrzésre vár") nem töri el némán a pontozást."""
    if not allapot:
        return False
    return "ellenorzes" in _ekezet_nelkul(allapot)


def rogzitsd_ellenorzest(db: Session, deliverable: Deliverable, employee: Employee) -> bool:
    """Feljegyzi, hogy ez az anyag ellenőrzésbe került. True, ha ÚJ esemény.

    Idempotens: ugyanahhoz az anyaghoz csak egyszer keletkezik esemény, tehát
    a ki-be kattintgatás nem termel pontot. A commitot a hívóra hagyjuk, hogy
    egy tranzakcióban maradjon az állapotváltással."""
    letezo = db.scalar(
        select(VagoEllenorzesEsemeny).where(VagoEllenorzesEsemeny.deliverable_id == deliverable.id)
    )
    if letezo is not None:
        return False
    db.add(
        VagoEllenorzesEsemeny(
            deliverable_id=deliverable.id,
            employee_id=employee.id,
            idopont=datetime.now(timezone.utc),
            allapot=deliverable.allapot,
        )
    )
    return True


def honap_hatarai(ev: int, honap: int) -> tuple[datetime, datetime]:
    """A hónap [kezdet, vég) határa időbélyegként, UTC-ben."""
    kezdet = datetime(ev, honap, 1, tzinfo=timezone.utc)
    veg = datetime(ev + (honap == 12), 1 if honap == 12 else honap + 1, 1, tzinfo=timezone.utc)
    return kezdet, veg


@dataclass
class Allas:
    """Egy versenyző állása egy hónapban."""

    employee_id: int
    nev: str
    #: Hány anyagot tett ellenőrzésbe, és az abból járó pont.
    ellenorzes_db: int = 0
    ellenorzes_pont: int = 0
    #: Vágással töltött percek és az abból járó pont.
    vagas_perc: float = 0.0
    vagas_pont: int = 0
    #: A kettő összege, arányosítás ELŐTT.
    nyers_pont: int = 0
    #: Ennyi munkanapja volt (beállítás vagy az alapérték).
    munkanap: int = ALAP_MUNKANAP
    #: A verseny hivatalos pontszáma: nyers x (20 / munkanap).
    pont: int = 0
    #: Hányadik helyen áll. 1-től, holtversenynél azonos hely.
    helyezes: int = 0


def _percek_honapra(db: Session, kezdet: datetime, veg: datetime) -> dict[int, float]:
    """Emberenként a hónapban vágással töltött percek.

    A mérés a START dátuma szerint tartozik egy hónapba: az éjfélen átnyúló
    munka annál a napnál marad, amikor elkezdték - így egyetlen mérés sem
    hasad ketté, és a napi/havi összegek is stimmelnek egymással.

    A `time_minutes` erősebb a start/end különbségénél: a lezáráskor oda kerül
    a végleges érték, és a kézzel javított időt is az őrzi (lásd
    services/deliverable_actions.py)."""
    sorok = db.scalars(
        select(Timesheet).where(Timesheet.start_date >= kezdet, Timesheet.start_date < veg)
    ).all()
    eredmeny: dict[int, float] = {}
    for t in sorok:
        percek = float(t.time_minutes) if t.time_minutes is not None else float(t.idotartam_perc or 0)
        if percek <= 0:
            continue
        eredmeny[t.employee_id] = eredmeny.get(t.employee_id, 0.0) + percek
    return eredmeny


def _helyezesek(allasok: list[Allas]) -> None:
    """Helyezés beírása. Holtversenynél AZONOS hely, és a következő hely
    ugyanannyival ugrik (1., 1., 3.) - egy versenyben a holtverseny nem
    dönthető el önkényesen, mondjuk névsor szerint.

    Aki 0 ponton áll, az nem kap helyezést: a "17. helyezett 0 ponttal" nem
    eredmény, csak zaj a listán."""
    elozo_pont: int | None = None
    elozo_hely = 0
    for i, a in enumerate(allasok, start=1):
        if a.pont <= 0:
            a.helyezes = 0
            continue
        if a.pont == elozo_pont:
            a.helyezes = elozo_hely
        else:
            a.helyezes = i
            elozo_hely = i
            elozo_pont = a.pont


def honap_allasa(db: Session, ev: int, honap: int) -> list[Allas]:
    """Egy hónap teljes állása, a legtöbb ponttal elöl.

    Mindenki bekerül, akinek AZ ADOTT HÓNAPBAN volt teljesítménye vagy
    beállított munkanapja - nem az összes munkatárs. Egy verseny listáján a
    nulla pontos nevek csak elfedik, kik versenyeznek valójában."""
    kezdet, veg = honap_hatarai(ev, honap)

    esemenyek = db.scalars(
        select(VagoEllenorzesEsemeny).where(
            VagoEllenorzesEsemeny.idopont >= kezdet, VagoEllenorzesEsemeny.idopont < veg
        )
    ).all()
    percek = _percek_honapra(db, kezdet, veg)
    napok = {
        n.employee_id: n
        for n in db.scalars(select(VagoJatekNap).where(VagoJatekNap.ev == ev, VagoJatekNap.honap == honap)).all()
    }

    erintett: set[int] = set(percek) | {e.employee_id for e in esemenyek} | set(napok)
    if not erintett:
        return []
    nevek = {
        e.id: e.full_name for e in db.scalars(select(Employee).where(Employee.id.in_(erintett))).all()
    }

    allasok: list[Allas] = []
    for employee_id in erintett:
        sajat_esemenyek = [e for e in esemenyek if e.employee_id == employee_id]
        vagas_perc = percek.get(employee_id, 0.0)
        munkanap = napok[employee_id].munkanap if employee_id in napok else ALAP_MUNKANAP
        # 0 vagy negatív munkanap: az arányosítás nullával osztana. Aki egy
        # napot sem dolgozott, annak nincs mit arányosítani sem - marad a
        # nyers pont (ami ilyenkor jellemzően 0).
        szorzo = (ALAP_MUNKANAP / munkanap) if munkanap > 0 else 1.0

        a = Allas(
            employee_id=employee_id,
            nev=nevek.get(employee_id, f"#{employee_id}"),
            ellenorzes_db=len(sajat_esemenyek),
            ellenorzes_pont=len(sajat_esemenyek) * ELLENORZES_PONT,
            vagas_perc=vagas_perc,
            # Lefelé kerekítünk: a megkezdett 3 perc még nem teljes pont.
            vagas_pont=int(vagas_perc // PERC_PER_PONT),
            munkanap=munkanap,
        )
        a.nyers_pont = a.ellenorzes_pont + a.vagas_pont
        a.pont = round(a.nyers_pont * szorzo)
        allasok.append(a)

    # Azonos pontnál névsor - hogy a lista sorrendje ne ugráljon lekérésenként.
    allasok.sort(key=lambda x: (-x.pont, x.nev))
    _helyezesek(allasok)
    return allasok


def honap_beallitas(db: Session, ev: int, honap: int) -> VagoJatekHonap | None:
    return db.scalar(select(VagoJatekHonap).where(VagoJatekHonap.ev == ev, VagoJatekHonap.honap == honap))


def elozo_honapok(ev: int, honap: int, darab: int) -> list[tuple[int, int]]:
    """Az adott hónapot MEGELŐZŐ `darab` hónap, a legfrissebbel elöl."""
    eredmeny: list[tuple[int, int]] = []
    e, h = ev, honap
    for _ in range(darab):
        elso = date(e, h, 1) - timedelta(days=1)
        e, h = elso.year, elso.month
        eredmeny.append((e, h))
    return eredmeny
