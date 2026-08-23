"""A HYPE 2026 diszpótábla HTTP-felülete: munkalapok, rács, cella-szerkesztés.

A rács TÖMÖREN megy ki: a cellák nem objektumok, hanem `[sor, oszlop, érték,
szín]` négyesek. A külsős munkalap 34 ezer cellája objektumokként több
megabájt volna minden oldalbetöltésnél - és pont ez az a felület, amit egész
nap nyitva tartanak.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import check_page_action, get_current_user, require_page_action
from app.models.diszpo_tabla import (
    SZINEK,
    DiszpoCella,
    DiszpoMunkalap,
    DiszpoOszlop,
    DiszpoSor,
)
from app.models.employee import Employee
from app.services import munkanap_szamlalo

router = APIRouter(prefix="/diszpo-tabla", tags=["diszpo-tabla"])

PAGE = "/diszpo-tabla"
#: A napidíj és a plusz napok ehhez az oldalhoz kötöttek: az bér-adat, nem
#: beosztás (a felhasználó kifejezett kérése).
PENZUGY_PAGE = "/penzugyek"


class MunkalapFej(BaseModel):
    id: int
    nev: str
    sorrend: int
    sor_szam: int
    oszlop_szam: int
    fejlec_sorok: int

    model_config = {"from_attributes": True}


class OszlopOut(BaseModel):
    idx: int
    cimke: str | None = None
    csoport: str | None = None
    employee_id: int | None = None
    employee_nev: str | None = None


class SorOut(BaseModel):
    idx: int
    datum: date | None = None
    nap: str | None = None
    diszposzam: int | None = None
    elvalaszto: bool = False


class MunkalapOut(MunkalapFej):
    oszlopok: list[OszlopOut]
    sorok: list[SorOut]
    #: [sor_idx, oszlop_idx, érték, szín] - lásd a modul leírását.
    cellak: list[tuple[int, int, str | None, str | None]]


@router.get("", response_model=list[MunkalapFej])
def list_munkalapok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A fülek - a rács tartalma nélkül."""
    return [
        MunkalapFej.model_validate(m)
        for m in db.scalars(select(DiszpoMunkalap).order_by(DiszpoMunkalap.sorrend, DiszpoMunkalap.id)).all()
    ]


def _munkalap_vagy_404(db: Session, munkalap_id: int) -> DiszpoMunkalap:
    m = db.get(DiszpoMunkalap, munkalap_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Ez a munkalap nem található.")
    return m


@router.get("/{munkalap_id}", response_model=MunkalapOut)
def get_munkalap(munkalap_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    m = _munkalap_vagy_404(db, munkalap_id)
    oszlopok = db.scalars(
        select(DiszpoOszlop)
        .options(selectinload(DiszpoOszlop.employee))
        .where(DiszpoOszlop.munkalap_id == m.id)
        .order_by(DiszpoOszlop.idx)
    ).all()
    sorok = db.scalars(
        select(DiszpoSor).where(DiszpoSor.munkalap_id == m.id).order_by(DiszpoSor.idx)
    ).all()
    cellak = db.execute(
        select(DiszpoCella.sor_idx, DiszpoCella.oszlop_idx, DiszpoCella.ertek, DiszpoCella.szin)
        .where(DiszpoCella.munkalap_id == m.id)
        .order_by(DiszpoCella.sor_idx, DiszpoCella.oszlop_idx)
    ).all()
    return MunkalapOut(
        **MunkalapFej.model_validate(m).model_dump(),
        oszlopok=[
            OszlopOut(
                idx=o.idx,
                cimke=o.cimke,
                csoport=o.csoport,
                employee_id=o.employee_id,
                employee_nev=o.employee.full_name if o.employee else None,
            )
            for o in oszlopok
        ],
        sorok=[
            SorOut(idx=s.idx, datum=s.datum, nap=s.nap, diszposzam=s.diszposzam, elvalaszto=s.elvalaszto)
            for s in sorok
        ],
        cellak=[(r, c, e, sz) for r, c, e, sz in cellak],
    )


class CellaIn(BaseModel):
    """Egy cella tartalma és/vagy színe.

    A `None` és a "nincs megadva" itt KÜLÖNBÖZIK: a szín törléséhez a `szin`
    mezőt kifejezetten `null`-ra kell állítani, míg a kihagyása azt jelenti,
    hogy maradjon, ami volt."""

    sor_idx: int
    oszlop_idx: int
    ertek: str | None = None
    szin: str | None = None
    #: Melyik mezőt akarjuk állítani. Enélkül egy szín-átállítás letörölné a
    #: cella szövegét (a felület a színpalettáról nem küld szöveget).
    ertek_valtozik: bool = False
    szin_valtozik: bool = False


def _egy_cella(db: Session, m: DiszpoMunkalap, adat: CellaIn) -> None:
    cella = db.scalar(
        select(DiszpoCella).where(
            DiszpoCella.munkalap_id == m.id,
            DiszpoCella.sor_idx == adat.sor_idx,
            DiszpoCella.oszlop_idx == adat.oszlop_idx,
        )
    )
    if cella is None:
        cella = DiszpoCella(munkalap_id=m.id, sor_idx=adat.sor_idx, oszlop_idx=adat.oszlop_idx)
        db.add(cella)
    if adat.ertek_valtozik:
        cella.ertek = (adat.ertek or "").strip() or None
    if adat.szin_valtozik:
        cella.szin = adat.szin
    if cella.ertek is None and cella.szin is None and cella.id is not None:
        db.delete(cella)


def _ellenoriz_cellat(m: DiszpoMunkalap, adat: CellaIn) -> None:
    if adat.szin_valtozik and adat.szin is not None and adat.szin not in SZINEK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen szín. Választható: {', '.join(SZINEK)}")
    if not (0 <= adat.sor_idx < max(m.sor_szam, 1) + 500) or not (0 <= adat.oszlop_idx < m.oszlop_szam + 50):
        raise HTTPException(status_code=400, detail="A cella a munkalapon kívülre esik.")


@router.put("/{munkalap_id}/cella", response_model=MunkalapOut | None)
def set_cella(
    munkalap_id: int,
    payload: CellaIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy cella szerkesztése. Üres cellához nem tartozik sor - ha mindkét
    mezője kiürül, a sort töröljük."""
    m = _munkalap_vagy_404(db, munkalap_id)
    _ellenoriz_cellat(m, payload)
    _egy_cella(db, m, payload)
    # A szín MUNKANAP-ADAT: a következő önköltség-számítás már ezt lássa.
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


class CellakIn(BaseModel):
    """Több cella egyszerre - egy kijelölt TARTOMÁNY színezéséhez/törléséhez.

    Egy hét napjait egyesével színezni öt kör-utat jelentene; így egy."""

    cellak: list[CellaIn]


@router.put("/{munkalap_id}/cellak", response_model=None)
def set_cellak(
    munkalap_id: int,
    payload: CellakIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    m = _munkalap_vagy_404(db, munkalap_id)
    if len(payload.cellak) > 5000:
        raise HTTPException(status_code=400, detail="Egyszerre legfeljebb 5000 cella módosítható.")
    for adat in payload.cellak:
        _ellenoriz_cellat(m, adat)
        _egy_cella(db, m, adat)
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


# ── SOR- ÉS OSZLOPMŰVELETEK ─────────────────────────────────────────────────
#
# A beszúrás/törlés az INDEXEKET tolja el. Ezt nem lehet naivan egy
# `idx = idx + 1` utasítással megtenni: az egyediségi megkötés (munkalap+idx)
# menet közben sérülne, mert a mozgó sor beleütközne a még nem mozdult
# szomszédjába. Ezért KÉT lépésben toljuk: előbb egy nagy eltolással
# "félretesszük" az érintett tartományt, majd onnan visszahozzuk a helyére. Így
# egyik lépésben sincs ütközés, és mindkettő EGY utasítás - egy 146 oszlopos
# munkalapon a soronkénti mozgatás több tízezer UPDATE lenne.

#: Ekkora eltolással tesszük félre az indexeket - jóval a valós tartomány
#: fölött, hogy biztosan ne ütközzön semmivel.
_FELRETESZ = 1_000_000


def _tolas(db: Session, modell, munkalap_id: int, oszlop, hatar: int, mennyivel: int) -> None:
    """A `hatar`-tól kezdődő indexek eltolása `mennyivel`-lel, ütközés nélkül."""
    db.query(modell).filter(modell.munkalap_id == munkalap_id, oszlop >= hatar).update(
        {oszlop: oszlop + _FELRETESZ}, synchronize_session=False
    )
    db.query(modell).filter(modell.munkalap_id == munkalap_id, oszlop >= _FELRETESZ).update(
        {oszlop: oszlop - _FELRETESZ + mennyivel}, synchronize_session=False
    )


class BeszurasIn(BaseModel):
    """Hova szúrjunk be. `ala=False` = a megadott index HELYÉRE (fölé)."""

    idx: int
    ala: bool = False


@router.post("/{munkalap_id}/sor", response_model=None)
def sor_beszurasa(
    munkalap_id: int,
    payload: BeszurasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Új, üres sor beszúrása - mint a táblázatban."""
    m = _munkalap_vagy_404(db, munkalap_id)
    hova = payload.idx + (1 if payload.ala else 0)
    if not 0 <= hova <= m.sor_szam:
        raise HTTPException(status_code=400, detail="A sor a munkalapon kívülre esne.")
    _tolas(db, DiszpoCella, m.id, DiszpoCella.sor_idx, hova, 1)
    _tolas(db, DiszpoSor, m.id, DiszpoSor.idx, hova, 1)
    db.add(DiszpoSor(munkalap_id=m.id, idx=hova))
    m.sor_szam += 1
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


@router.delete("/{munkalap_id}/sor/{idx}", response_model=None)
def sor_torlese(
    munkalap_id: int,
    idx: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Egy sor törlése a tartalmával együtt - a többi sor feljebb csúszik."""
    m = _munkalap_vagy_404(db, munkalap_id)
    if not 0 <= idx < m.sor_szam:
        raise HTTPException(status_code=400, detail="Ez a sor nem létezik.")
    db.query(DiszpoCella).filter(DiszpoCella.munkalap_id == m.id, DiszpoCella.sor_idx == idx).delete(
        synchronize_session=False
    )
    db.query(DiszpoSor).filter(DiszpoSor.munkalap_id == m.id, DiszpoSor.idx == idx).delete(
        synchronize_session=False
    )
    _tolas(db, DiszpoCella, m.id, DiszpoCella.sor_idx, idx + 1, -1)
    _tolas(db, DiszpoSor, m.id, DiszpoSor.idx, idx + 1, -1)
    m.sor_szam = max(m.sor_szam - 1, 0)
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


@router.post("/{munkalap_id}/oszlop", response_model=None)
def oszlop_beszurasa(
    munkalap_id: int,
    payload: BeszurasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Új, üres oszlop beszúrása. A csoportot (szekciót) a bal szomszédtól
    örökli - a Sheetben is oda tartozik, ahova beszúrták."""
    m = _munkalap_vagy_404(db, munkalap_id)
    hova = payload.idx + (1 if payload.ala else 0)
    if not 0 <= hova <= m.oszlop_szam:
        raise HTTPException(status_code=400, detail="Az oszlop a munkalapon kívülre esne.")
    bal = db.scalar(
        select(DiszpoOszlop).where(DiszpoOszlop.munkalap_id == m.id, DiszpoOszlop.idx == max(hova - 1, 0))
    )
    _tolas(db, DiszpoCella, m.id, DiszpoCella.oszlop_idx, hova, 1)
    _tolas(db, DiszpoOszlop, m.id, DiszpoOszlop.idx, hova, 1)
    db.add(DiszpoOszlop(munkalap_id=m.id, idx=hova, csoport=bal.csoport if bal else None))
    m.oszlop_szam += 1
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


@router.delete("/{munkalap_id}/oszlop/{idx}", response_model=None)
def oszlop_torlese(
    munkalap_id: int,
    idx: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Egy oszlop törlése a tartalmával együtt."""
    m = _munkalap_vagy_404(db, munkalap_id)
    if not 0 <= idx < m.oszlop_szam:
        raise HTTPException(status_code=400, detail="Ez az oszlop nem létezik.")
    db.query(DiszpoCella).filter(DiszpoCella.munkalap_id == m.id, DiszpoCella.oszlop_idx == idx).delete(
        synchronize_session=False
    )
    db.query(DiszpoOszlop).filter(DiszpoOszlop.munkalap_id == m.id, DiszpoOszlop.idx == idx).delete(
        synchronize_session=False
    )
    _tolas(db, DiszpoCella, m.id, DiszpoCella.oszlop_idx, idx + 1, -1)
    _tolas(db, DiszpoOszlop, m.id, DiszpoOszlop.idx, idx + 1, -1)
    m.oszlop_szam = max(m.oszlop_szam - 1, 0)
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    return None


class SorAdatIn(BaseModel):
    """A sor SAJÁT adatai - amiket nem cellaként tárolunk.

    A dátum azért fontos, mert ebből számoljuk a munkanapokat: egy új sor
    addig nem tartozik egyetlen naphoz sem."""

    datum: date | None = None
    datum_valtozik: bool = False


@router.put("/{munkalap_id}/sor/{idx}", response_model=SorOut)
def sor_adat(
    munkalap_id: int,
    idx: int,
    payload: SorAdatIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    m = _munkalap_vagy_404(db, munkalap_id)
    sor = db.scalar(select(DiszpoSor).where(DiszpoSor.munkalap_id == m.id, DiszpoSor.idx == idx))
    if sor is None:
        raise HTTPException(status_code=404, detail="Ez a sor nem található.")
    if payload.datum_valtozik:
        sor.datum = payload.datum
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    db.refresh(sor)
    return SorOut(idx=sor.idx, datum=sor.datum, nap=sor.nap, diszposzam=sor.diszposzam, elvalaszto=sor.elvalaszto)


class OszlopKotesIn(BaseModel):
    """Melyik munkatárs oszlopa ez. `employee_id=None` = a kötés törlése."""

    employee_id: int | None = None
    #: Az oszlop felirata (a fejlécben). None + `cimke_valtozik` = törlés.
    cimke: str | None = None
    cimke_valtozik: bool = False


@router.put("/{munkalap_id}/oszlop/{idx}", response_model=OszlopOut)
def set_oszlop_kotes(
    munkalap_id: int,
    idx: int,
    payload: OszlopKotesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Az oszlop hozzákötése egy munkatárshoz.

    Enélkül az oszlop színei nem számítanak bele a munkanap-számlálásba: a
    "GERI" felirat nekünk nem azonosít senkit. Az import csak akkor köt, ha a
    név EGYÉRTELMŰ - a többit itt lehet megadni."""
    _munkalap_vagy_404(db, munkalap_id)
    oszlop = db.scalar(
        select(DiszpoOszlop).where(DiszpoOszlop.munkalap_id == munkalap_id, DiszpoOszlop.idx == idx)
    )
    if oszlop is None:
        raise HTTPException(status_code=404, detail="Ez az oszlop nem található.")
    if payload.employee_id is not None and db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=404, detail="Ez a munkatárs nem található.")
    oszlop.employee_id = payload.employee_id
    if payload.cimke_valtozik:
        oszlop.cimke = (payload.cimke or "").strip() or None
    munkanap_szamlalo.urits_gyorsitotar(db)
    db.commit()
    db.refresh(oszlop)
    return OszlopOut(
        idx=oszlop.idx,
        cimke=oszlop.cimke,
        csoport=oszlop.csoport,
        employee_id=oszlop.employee_id,
        employee_nev=oszlop.employee.full_name if oszlop.employee else None,
    )


class HaviAllasOut(BaseModel):
    """Hol tart valaki a szerződött napjaival egy hónapban.

    A PÉNZ-részt (napidíj, plusz napok, szerződött napszám) csak az kapja meg,
    aki a Pénzügyek oldalt is látja - lásd `_lathatja_a_penzugyet`. Aki nem, az
    a puszta munkanap-számot látja: az beosztási adat, nem bér."""

    employee_id: int
    employee_nev: str | None = None
    ev: int
    honap: int
    munkanapok: int
    szerzodott_napok: int | None = None
    napi_dij: float | None = None
    plusz_nap_napi_dij: float | None = None
    #: Az a nap, amelyiken a szerződött napok elfogynak (az utolsó "benne van
    #: a bérben" nap). None, ha nincs napszám, vagy nem jött össze annyi nap.
    hatarnap: date | None = None
    #: A szerződött napokon FELÜLI munkanapok.
    plusz_napok: list[date] = []
    #: Megkapta-e a hívó a pénzügyi részt. A felület ebből tudja, hogy egy üres
    #: napidíj "nincs megadva" vagy "nem látod" - a kettő nem ugyanaz.
    penzugyi_adat: bool = False


def _lathatja_a_penzugyet(db: Session, employee: Employee) -> bool:
    """Látja-e a Pénzügyek oldalt. UGYANAZ a szabály, ami ott is véd - nem egy
    második, külön karbantartott lista (lásd core/security.check_page_action)."""
    try:
        check_page_action(db, employee, PENZUGY_PAGE, "view")
        return True
    except HTTPException:
        return False


@router.get("/munkanapok/{ev}/{honap}", response_model=list[HaviAllasOut])
def havi_allas(
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Ki hány napot dolgozott ebben a hónapban - és kinél fogyott el a
    szerződött napszám.

    Csak azok szerepelnek, akiknek van oszlopuk a diszpótáblában: akiről nincs
    adat, arról nem is állítunk semmit.

    A NAPIDÍJ ÉS A PLUSZ NAPOK a Pénzügyek jogosultságához kötöttek. Ezt a
    SZERVER dönti el, nem a felület: egy elrejtett oszlop attól még ott lenne a
    válaszban, és a böngésző hálózati fülén bárki elolvasná."""
    if not 1 <= honap <= 12:
        raise HTTPException(status_code=400, detail="A hónap 1 és 12 közötti szám.")
    penz = _lathatja_a_penzugyet(db, user)
    employee_idk = set(munkanap_szamlalo.munkanap_terkep(db).keys())
    if not employee_idk:
        return []
    emberek = db.scalars(select(Employee).where(Employee.id.in_(employee_idk))).all()
    eredmeny: list[HaviAllasOut] = []
    for emb in emberek:
        kep = munkanap_szamlalo.havi_munkanapok(db, emb, ev, honap)
        if not kep.napok:
            continue
        eredmeny.append(
            HaviAllasOut(
                employee_id=emb.id,
                employee_nev=emb.full_name,
                ev=ev,
                honap=honap,
                munkanapok=kep.darab,
                penzugyi_adat=penz,
                szerzodott_napok=kep.szerzodott_napok if penz else None,
                napi_dij=float(emb.napi_dij) if penz and emb.napi_dij is not None else None,
                plusz_nap_napi_dij=(
                    float(emb.plusz_nap_napi_dij) if penz and emb.plusz_nap_napi_dij is not None else None
                ),
                hatarnap=kep.hatarnap if penz else None,
                plusz_napok=kep.plusz_napok if penz else [],
            )
        )
    eredmeny.sort(key=lambda a: (-a.munkanapok, a.employee_nev or ""))
    return eredmeny
