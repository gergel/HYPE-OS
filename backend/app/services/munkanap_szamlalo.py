"""MUNKANAP-SZÁMLÁLÁS a diszpótáblából - és mikor fogy el a szerződött nap.

A belsős munkatárs nem "amennyit kell" napra van szerződve, hanem egy
megbeszélt HAVI NAPSZÁMRA: annyi nap benne van a havi bérében. Ami e fölött
van, az plusz munka, aminek külön díja van - és a projekt önköltségébe is azon
az áron kell beszámítani, különben egy hónap végi forgatás olcsóbbnak
látszana, mint amennyibe került (lásd services/belsos_koltseg.py).

MI SZÁMÍT MUNKANAPNAK? A diszpótábla cellájának SZÍNE mondja meg (lásd
models/diszpo_tabla.py):

- **zöld** - aznap dolgozott;
- **kék** - a vágóknál ugyanúgy munkanap, csak irodában (a zöld náluk a terep);
- **fehér** - munkanap volt, de nem tudtunk neki munkát adni. EZ IS MUNKANAP:
  a napja le volt kötve, tehát a szerződött napokból ugyanúgy fogy.

A piros (szabadnap) és a szürke (akkor még nem dolgozott nálunk) nem számít.

EGY NAP EGY MUNKANAP, akkor is, ha aznap két diszpó volt (a táblázatban két
sor tartozik ugyanahhoz a naphoz). A szerződés napokról szól, nem diszpókról.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.diszpo_tabla import MUNKANAP_SZINEK, DiszpoCella, DiszpoOszlop, DiszpoSor


@dataclass
class HaviMunkanapok:
    """Egy ember egy hónapja: mely napokon dolgozott, és hol a határ."""

    employee_id: int
    ev: int
    honap: int
    #: A munkanapok NÖVEKVŐ sorrendben - ebből derül ki, hányadikán fogy el a
    #: szerződött napok száma.
    napok: list[date] = field(default_factory=list)
    #: Hány napra van szerződve (None = nincs megadva, tehát nincs korlát).
    szerzodott_napok: int | None = None

    @property
    def darab(self) -> int:
        return len(self.napok)

    @property
    def hatarnap(self) -> date | None:
        """Az a nap, amelyiken a szerződött napok ELFOGYNAK - vagyis a
        szerződés szerinti UTOLSÓ nap. Az ezt KÖVETŐ munkanapok a pluszok.

        None, ha nincs megadva napszám, vagy ha a hónapban ennyi munkanap
        össze sem jött."""
        if self.szerzodott_napok is None or self.szerzodott_napok <= 0:
            return None
        if len(self.napok) < self.szerzodott_napok:
            return None
        return self.napok[self.szerzodott_napok - 1]

    @property
    def plusz_napok(self) -> list[date]:
        """A szerződött napokon FELÜLI munkanapok."""
        if self.szerzodott_napok is None or self.szerzodott_napok <= 0:
            return []
        return self.napok[self.szerzodott_napok :]

    def plusz_nap_e(self, nap: date) -> bool:
        """Erre a napra a PLUSZ napi díj jár-e?

        Az a nap plusz, ami a szerződött napok elfogyása UTÁN van. Egy olyan
        nap, ami nincs is a táblázatban (nincs kiszínezve), NEM plusz nap: arról
        nem tudjuk, hogy munkanap volt-e, és egy nem tudott dolog nem drágíthat
        meg egy projektet."""
        return nap in set(self.plusz_napok)


#: A kérésen belüli gyorsítótár kulcsa a Session `info` szótárában.
_TERKEP_KULCS = "munkanap_terkep"


def _betolt(db: Session) -> dict[int, list[date]]:
    sorok = db.execute(
        select(DiszpoOszlop.employee_id, DiszpoSor.datum)
        .select_from(DiszpoCella)
        .join(
            DiszpoOszlop,
            (DiszpoOszlop.munkalap_id == DiszpoCella.munkalap_id) & (DiszpoOszlop.idx == DiszpoCella.oszlop_idx),
        )
        .join(
            DiszpoSor,
            (DiszpoSor.munkalap_id == DiszpoCella.munkalap_id) & (DiszpoSor.idx == DiszpoCella.sor_idx),
        )
        .where(
            DiszpoOszlop.employee_id.is_not(None),
            DiszpoCella.szin.in_(sorted(MUNKANAP_SZINEK)),
            DiszpoSor.datum.is_not(None),
        )
    ).all()
    # Egy nap egy munkanap - a két diszpós napok két sora ugyanaz a nap.
    halmazok: dict[int, set[date]] = {}
    for employee_id, datum in sorok:
        halmazok.setdefault(employee_id, set()).add(datum)
    return {eid: sorted(napok) for eid, napok in halmazok.items()}


def munkanap_terkep(db: Session) -> dict[int, list[date]]:
    """munkatárs -> a munkanapjai, időrendben. EGY lekérdezésből, KÉRÉSENKÉNT
    egyszer.

    Miért nem emberenként/naponként kérdezünk? Mert a napidíj a projektek
    ÖNKÖLTSÉGÉBE megy, azt pedig a projektkód-lista mind a több száz sorára
    kiszámoljuk: soronkénti lekérdezésből percekig töltő oldal lenne. A teljes
    munkanap-halmaz viszont pár ezer sor, egyben elfér.

    A gyorsítótár a Session `info` szótárában él, tehát pontosan egy kérésig -
    egy szerkesztés utáni következő kérés már a friss adatot látja."""
    terkep = db.info.get(_TERKEP_KULCS)
    if terkep is None:
        terkep = _betolt(db)
        db.info[_TERKEP_KULCS] = terkep
    return terkep


def urits_gyorsitotar(db: Session) -> None:
    """A cella szerkesztése után a következő számítás már ne a régit lássa."""
    db.info.pop(_TERKEP_KULCS, None)


def havi_munkanapok(db: Session, employee, ev: int, honap: int) -> HaviMunkanapok:
    """Egy ember munkanapjai egy hónapban, a diszpótábla színei szerint."""
    mind = munkanap_terkep(db).get(employee.id, [])
    napok = [n for n in mind if (n.year, n.month) == (ev, honap)]
    return HaviMunkanapok(
        employee_id=employee.id,
        ev=ev,
        honap=honap,
        napok=napok,
        szerzodott_napok=employee.szerzodott_napok,
    )


def napi_dij_a_napra(db: Session, employee, nap: date | None) -> float:
    """Mennyibe kerül EZ a nap ettől az embertől?

    A rendes napidíj - kivéve, ha aznap már a szerződött napokon FELÜL
    dolgozott: olyankor a plusz nap díja.

    Óvatosan, ebben a sorrendben esünk vissza:

    1. nincs napidíj megadva -> 0 (nem tippelünk összeget);
    2. nincs szerződött napszám, vagy nincs plusz napi díj -> rendes napidíj
       (a hiányzó adat nem árazhat át semmit csendben);
    3. a nap nincs a szerződött napokon felül -> rendes napidíj;
    4. különben a PLUSZ napi díj."""
    alap = float(employee.napi_dij) if employee.napi_dij else 0.0
    if not alap or nap is None:
        return alap
    if not employee.szerzodott_napok or employee.plusz_nap_napi_dij is None:
        return alap
    kep = havi_munkanapok(db, employee, nap.year, nap.month)
    return float(employee.plusz_nap_napi_dij) if kep.plusz_nap_e(nap) else alap
