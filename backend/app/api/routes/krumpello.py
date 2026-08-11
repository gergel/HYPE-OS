"""Krumpello - önálló pénzügyi felület a HYPE OS-en belül.

Külön jogosultsági oldal ("/krumpello"): a Beállítások alatt egyenként adható
meg, ki látja egyáltalán a Krumpello kapcsolót és ki léphet át ide. Ez
szándékosan NEM a Pénzügyek joga: aki a produkciós pénzügyeket viszi, nem
feltétlenül tartozik rá a bolt kasszája - és fordítva.

Miért nem a generikus CRUD-gyár? Mert három dolog itt tényleg egyedi: a napi
kassza naponta EGY sor (upsert, nem "új rekord"), a munkaóra fizetése magától
kiszámolódik, ha üresen hagyják, és a lista-végpontok mellé egy összesítő is
kell, ami egyszerre több táblából dolgozik. Ezek a gyár elé kívánkoznak, nem
utána - lásd api/crud_router.py leírását arról, mikor éri meg kézzel írni.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee
from app.models.krumpello import (
    KIADAS_FORRASOK,
    KrumpelloDolgozo,
    KrumpelloKiadas,
    KrumpelloMunkaora,
    KrumpelloNap,
)
from app.models.user_access import PageAccessConfig
from app.services import krumpello_osszesito

router = APIRouter(prefix="/krumpello", tags=["krumpello"])

PAGE = "/krumpello"


def lathatja(db: Session, employee: Employee) -> bool:
    """Látja-e ez az ember a Krumpellót?

    Ugyanaz a szabály, mint az oldal-láthatóságnál mindenhol máshol (lásd
    models/user_access.py és routes/user_access.get_my_access): ha admin NEM
    állított be neki oldal-korlátozást, mindent lát; ha beállított, akkor
    ennek az oldalnak szerepelnie kell a kulcsok között.

    Azért van külön függvényben, mert két helyen kell: a GET végpontok
    kapujaként, és a fejlécben ülő kapcsolónak (lásd /hozzaferes) - ott
    ugyanis nem hibát kell dobni, hanem igen/nem választ adni."""
    config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
    if config is None or config.page_permissions is None:
        return True
    return PAGE in config.page_permissions


def olvashat(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)) -> Employee:
    """A GET végpontok kapuja.

    SZÁNDÉKOSAN nem require_page_action: az írási szerepkört (admin/operator)
    követelné meg, tehát egy csak-olvasó fiók a saját, engedélyezett oldalát
    sem érné el. Az írás továbbra is require_page_action mögött van."""
    if not lathatja(db, user):
        raise HTTPException(status_code=403, detail="Nincs jogosultságod a Krumpello megtekintéséhez.")
    return user


def _f(ertek) -> float | None:
    return float(ertek) if ertek is not None else None


# ─────────────────────────────────────────────────────────────────────────────
# Napi kassza
# ─────────────────────────────────────────────────────────────────────────────


class NapIn(BaseModel):
    datum: date
    brutto_kp: float | None = None
    brutto_kartya: float | None = None
    netto_kp: float | None = None
    netto_kartya: float | None = None
    borravalo_kp: float | None = None
    borravalo_kartya: float | None = None
    extra: float | None = None
    megjegyzes: str | None = None


class NapRead(BaseModel):
    id: int
    datum: date
    brutto_kp: float | None = None
    brutto_kartya: float | None = None
    netto_kp: float | None = None
    netto_kartya: float | None = None
    borravalo_kp: float | None = None
    borravalo_kartya: float | None = None
    extra: float | None = None
    megjegyzes: str | None = None
    #: Számított mezők - a felület ezekkel nem számol újra.
    brutto_osszesen: float = 0
    netto_osszesen: float = 0
    borravalo_osszesen: float = 0


def _nap_kimenet(nap: KrumpelloNap) -> NapRead:
    adat = NapRead(
        id=nap.id,
        datum=nap.datum,
        brutto_kp=_f(nap.brutto_kp),
        brutto_kartya=_f(nap.brutto_kartya),
        netto_kp=_f(nap.netto_kp),
        netto_kartya=_f(nap.netto_kartya),
        borravalo_kp=_f(nap.borravalo_kp),
        borravalo_kartya=_f(nap.borravalo_kartya),
        extra=_f(nap.extra),
        megjegyzes=nap.megjegyzes,
    )
    adat.brutto_osszesen = (adat.brutto_kp or 0) + (adat.brutto_kartya or 0)
    adat.netto_osszesen = (adat.netto_kp or 0) + (adat.netto_kartya or 0)
    adat.borravalo_osszesen = (adat.borravalo_kp or 0) + (adat.borravalo_kartya or 0)
    return adat


@router.get("/napok", response_model=list[NapRead])
def list_napok(
    tol: date | None = None,
    ig: date | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    """A napi kassza-zárások, a legfrissebb nappal elöl."""
    stmt = select(KrumpelloNap)
    if tol is not None:
        stmt = stmt.where(KrumpelloNap.datum >= tol)
    if ig is not None:
        stmt = stmt.where(KrumpelloNap.datum <= ig)
    return [_nap_kimenet(n) for n in db.scalars(stmt.order_by(KrumpelloNap.datum.desc())).all()]


@router.put("/napok", response_model=NapRead)
def upsert_nap(
    payload: NapIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy nap zárása - ha már van sor arra a napra, azt írja felül.

    Szándékosan PUT és nem POST: naponta pontosan egy zárás van (lásd
    uq_krumpello_nap_datum). Ha ez "létrehozás" lenne, egy másodszor beküldött
    nap nyers egyediség-hibára futna, holott a felhasználó szándéka
    egyértelműen a javítás."""
    nap = db.scalar(select(KrumpelloNap).where(KrumpelloNap.datum == payload.datum))
    if nap is None:
        nap = KrumpelloNap(datum=payload.datum)
        db.add(nap)
    for mezo, ertek in payload.model_dump(exclude={"datum"}).items():
        setattr(nap, mezo, ertek)
    db.commit()
    db.refresh(nap)
    return _nap_kimenet(nap)


@router.delete("/napok/{nap_id}", status_code=204)
def delete_nap(
    nap_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    nap = db.get(KrumpelloNap, nap_id)
    if nap is None:
        raise HTTPException(status_code=404, detail="Ez a nap nem található.")
    db.delete(nap)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Kiadások
# ─────────────────────────────────────────────────────────────────────────────


class KiadasIn(BaseModel):
    forras: str
    kedvezmenyezett: str
    datum: date | None = None
    megnevezes: str | None = None
    netto: float | None = None
    afa: float | None = None
    brutto: float | None = None
    megjegyzes: str | None = None


class KiadasPatch(BaseModel):
    """Részleges módosítás: CSAK a ténylegesen elküldött mezőket írjuk át.

    Külön séma a felvitelitől, ahol a forrás és a kedvezményezett kötelező. Ha
    itt is azt használnánk, egy "csak az összeget javítom" kérés 422-vel esne
    el, mert a body-ból hiányzik a két kötelező mező - holott épp azokat nem
    akarjuk bántani."""

    forras: str | None = None
    kedvezmenyezett: str | None = None
    datum: date | None = None
    megnevezes: str | None = None
    netto: float | None = None
    afa: float | None = None
    brutto: float | None = None
    megjegyzes: str | None = None


class KiadasRead(KiadasIn):
    id: int


def _ellenorzott_forras(forras: str) -> str:
    if forras not in KIADAS_FORRASOK:
        raise HTTPException(
            status_code=400,
            detail=f"Ismeretlen forrás. Választható: {', '.join(KIADAS_FORRASOK)}",
        )
    return forras


def _kiadas_kimenet(k: KrumpelloKiadas) -> KiadasRead:
    return KiadasRead(
        id=k.id,
        forras=k.forras,
        kedvezmenyezett=k.kedvezmenyezett,
        datum=k.datum,
        megnevezes=k.megnevezes,
        netto=_f(k.netto),
        afa=_f(k.afa),
        brutto=_f(k.brutto),
        megjegyzes=k.megjegyzes,
    )


@router.get("/kiadasok", response_model=list[KiadasRead])
def list_kiadasok(
    forras: str | None = None,
    tol: date | None = None,
    ig: date | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    stmt = select(KrumpelloKiadas)
    if forras:
        stmt = stmt.where(KrumpelloKiadas.forras == _ellenorzott_forras(forras))
    if tol is not None:
        stmt = stmt.where(KrumpelloKiadas.datum >= tol)
    if ig is not None:
        stmt = stmt.where(KrumpelloKiadas.datum <= ig)
    # A dátum nélküli (még nem beazonosított) tételek a lista VÉGÉRE kerülnek,
    # nem az elejére: ott láthatók, de nem tolják el a friss tételeket.
    sorok = db.scalars(stmt).all()
    sorok = sorted(sorok, key=lambda k: (k.datum is None, -(k.datum.toordinal() if k.datum else 0), k.id))
    return [_kiadas_kimenet(k) for k in sorok]


@router.post("/kiadasok", response_model=KiadasRead, status_code=201)
def create_kiadas(
    payload: KiadasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    _ellenorzott_forras(payload.forras)
    if not payload.kedvezmenyezett.strip():
        raise HTTPException(status_code=400, detail="Add meg, kinek fizettünk.")
    k = KrumpelloKiadas(**payload.model_dump())
    db.add(k)
    db.commit()
    db.refresh(k)
    return _kiadas_kimenet(k)


@router.patch("/kiadasok/{kiadas_id}", response_model=KiadasRead)
def update_kiadas(
    kiadas_id: int,
    payload: KiadasPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    k = db.get(KrumpelloKiadas, kiadas_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Ez a kiadás nem található.")
    valtozas = payload.model_dump(exclude_unset=True)
    if "forras" in valtozas:
        _ellenorzott_forras(valtozas["forras"])
    for mezo, ertek in valtozas.items():
        setattr(k, mezo, ertek)
    db.commit()
    db.refresh(k)
    return _kiadas_kimenet(k)


@router.delete("/kiadasok/{kiadas_id}", status_code=204)
def delete_kiadas(
    kiadas_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    k = db.get(KrumpelloKiadas, kiadas_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Ez a kiadás nem található.")
    db.delete(k)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Dolgozók és munkaóra
# ─────────────────────────────────────────────────────────────────────────────


class DolgozoIn(BaseModel):
    nev: str
    alap_orabar: float | None = None
    aktiv: bool = True
    megjegyzes: str | None = None
    employee_id: int | None = None


class DolgozoRead(BaseModel):
    id: int
    nev: str
    alap_orabar: float | None = None
    aktiv: bool = True
    megjegyzes: str | None = None
    employee_id: int | None = None
    #: Összesítés a szűrt időszakra - a lista ebből mutatja, ki mennyit
    #: dolgozott, anélkül hogy a felület soronként összeadná.
    ora_osszesen: float = 0
    fizetes_osszesen: float = 0
    borravalo_osszesen: float = 0
    #: Ebből mennyit fizettünk már ki, és mennyi van még hátra. A "még jár" a
    #: gyakorlatban használt szám: ezt kell elutalni.
    kifizetve_osszesen: float = 0
    hatralek: float = 0
    #: Hány napja van még jelöletlenül - ebből látszik, van-e egyáltalán teendő.
    hatralekos_napok: int = 0
    #: Az utolsó nap, amikor dolgozott - ebből látszik, ki aktív MOST.
    utolso_nap: date | None = None


class DolgozoPatch(BaseModel):
    """Részleges módosítás - lásd KiadasPatch indoklását."""

    nev: str | None = None
    alap_orabar: float | None = None
    aktiv: bool | None = None
    megjegyzes: str | None = None
    employee_id: int | None = None


class MunkaoraIn(BaseModel):
    dolgozo_id: int
    datum: date
    ora: float | None = None
    orabar: float | None = None
    #: Üresen hagyva óra × órabér lesz belőle (lásd _szamolt_fizetes).
    fizetes: float | None = None
    borravalo: float | None = None
    megjegyzes: str | None = None


class MunkaoraPatch(BaseModel):
    """Részleges módosítás - lásd KiadasPatch indoklását.

    A dolgozó és a nap SZÁNDÉKOSAN nincs benne: egy meglévő sort nem lehet
    átrakni másik emberre vagy másik napra. Az ilyen javítás valójában
    "rossz helyre vittem fel" - ott a törlés és az új felvitel a helyes út,
    különben egy elgépelt kattintás némán elmozdítana egy már elszámolt
    munkanapot."""

    ora: float | None = None
    orabar: float | None = None
    fizetes: float | None = None
    borravalo: float | None = None
    megjegyzes: str | None = None
    kifizetve: bool | None = None
    kifizetes_datuma: date | None = None


class MunkaoraRead(BaseModel):
    id: int
    dolgozo_id: int
    dolgozo_nev: str
    datum: date
    ora: float | None = None
    orabar: float | None = None
    fizetes: float | None = None
    borravalo: float | None = None
    megjegyzes: str | None = None
    kifizetve: bool = False
    kifizetes_datuma: date | None = None


def _szamolt_fizetes(payload: MunkaoraIn) -> float | None:
    """A napra járó bér. A beküldött érték mindig erősebb: a kerekítés, a
    megbeszélt átalány és a pótlék így nem tűnik el egy automatizmus miatt
    (lásd models/krumpello.py KrumpelloMunkaora)."""
    if payload.fizetes is not None:
        return payload.fizetes
    if payload.ora is not None and payload.orabar is not None:
        return round(payload.ora * payload.orabar, 2)
    return None


def _munkaora_kimenet(m: KrumpelloMunkaora) -> MunkaoraRead:
    return MunkaoraRead(
        id=m.id,
        dolgozo_id=m.dolgozo_id,
        dolgozo_nev=m.dolgozo.nev if m.dolgozo else f"#{m.dolgozo_id}",
        datum=m.datum,
        ora=_f(m.ora),
        orabar=_f(m.orabar),
        fizetes=_f(m.fizetes),
        borravalo=_f(m.borravalo),
        megjegyzes=m.megjegyzes,
        kifizetve=m.kifizetve,
        kifizetes_datuma=m.kifizetes_datuma,
    )


@router.get("/dolgozok", response_model=list[DolgozoRead])
def list_dolgozok(
    tol: date | None = None,
    ig: date | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    """A dolgozók, a megadott időszakra összesített óráikkal.

    Az időszak alapból NINCS szűkítve: így a lista a teljes történetet mutatja.
    A felület havi szűrővel kéri le, mert az elszámolás havonta zárul."""
    dolgozok = db.scalars(select(KrumpelloDolgozo).order_by(KrumpelloDolgozo.aktiv.desc(), KrumpelloDolgozo.nev)).all()
    stmt = select(KrumpelloMunkaora)
    if tol is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum >= tol)
    if ig is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum <= ig)
    orak = db.scalars(stmt).all()

    eredmeny = []
    for d in dolgozok:
        sajat = [o for o in orak if o.dolgozo_id == d.id]
        eredmeny.append(
            DolgozoRead(
                id=d.id,
                nev=d.nev,
                alap_orabar=_f(d.alap_orabar),
                aktiv=d.aktiv,
                megjegyzes=d.megjegyzes,
                employee_id=d.employee_id,
                ora_osszesen=sum(_f(o.ora) or 0 for o in sajat),
                fizetes_osszesen=sum(_f(o.fizetes) or 0 for o in sajat),
                borravalo_osszesen=sum(_f(o.borravalo) or 0 for o in sajat),
                # A borravaló SZÁNDÉKOSAN nincs a hátralékban: az a vendégektől
                # jön, jellemzően aznap a kasszából kapják meg - nem a bérrel
                # együtt utaljuk (lásd models/krumpello.py).
                kifizetve_osszesen=sum(_f(o.fizetes) or 0 for o in sajat if o.kifizetve),
                hatralek=sum(_f(o.fizetes) or 0 for o in sajat if not o.kifizetve),
                hatralekos_napok=sum(1 for o in sajat if not o.kifizetve),
                utolso_nap=max((o.datum for o in sajat), default=None),
            )
        )
    return eredmeny


@router.post("/dolgozok", response_model=DolgozoRead, status_code=201)
def create_dolgozo(
    payload: DolgozoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    if not payload.nev.strip():
        raise HTTPException(status_code=400, detail="Add meg a dolgozó nevét.")
    d = KrumpelloDolgozo(**payload.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return DolgozoRead(
        id=d.id, nev=d.nev, alap_orabar=_f(d.alap_orabar), aktiv=d.aktiv,
        megjegyzes=d.megjegyzes, employee_id=d.employee_id,
    )


@router.patch("/dolgozok/{dolgozo_id}", response_model=DolgozoRead)
def update_dolgozo(
    dolgozo_id: int,
    payload: DolgozoPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    d = db.get(KrumpelloDolgozo, dolgozo_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Ez a dolgozó nem található.")
    for mezo, ertek in payload.model_dump(exclude_unset=True).items():
        setattr(d, mezo, ertek)
    db.commit()
    db.refresh(d)
    return DolgozoRead(
        id=d.id, nev=d.nev, alap_orabar=_f(d.alap_orabar), aktiv=d.aktiv,
        megjegyzes=d.megjegyzes, employee_id=d.employee_id,
    )


@router.get("/munkaorak", response_model=list[MunkaoraRead])
def list_munkaorak(
    dolgozo_id: int | None = None,
    tol: date | None = None,
    ig: date | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    """Ki mikor hány órát dolgozott, milyen órabéren - a legfrissebb nappal elöl."""
    stmt = select(KrumpelloMunkaora)
    if dolgozo_id is not None:
        stmt = stmt.where(KrumpelloMunkaora.dolgozo_id == dolgozo_id)
    if tol is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum >= tol)
    if ig is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum <= ig)
    sorok = db.scalars(stmt.order_by(KrumpelloMunkaora.datum.desc(), KrumpelloMunkaora.id)).all()
    return [_munkaora_kimenet(m) for m in sorok]


@router.post("/munkaorak", response_model=MunkaoraRead, status_code=201)
def create_munkaora(
    payload: MunkaoraIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    dolgozo = db.get(KrumpelloDolgozo, payload.dolgozo_id)
    if dolgozo is None:
        raise HTTPException(status_code=404, detail="Ez a dolgozó nem található.")
    adat = payload.model_dump()
    adat["fizetes"] = _szamolt_fizetes(payload)
    m = KrumpelloMunkaora(**adat)
    db.add(m)
    # Az utoljára használt órabér lesz a következő felvitel javaslata - így a
    # szokásos eset egy kattintás, a béremelés meg egyszeri átírás.
    if payload.orabar is not None:
        dolgozo.alap_orabar = payload.orabar
    db.commit()
    db.refresh(m)
    return _munkaora_kimenet(m)


@router.patch("/munkaorak/{munkaora_id}", response_model=MunkaoraRead)
def update_munkaora(
    munkaora_id: int,
    payload: MunkaoraPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    m = db.get(KrumpelloMunkaora, munkaora_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Ez a munkaóra-sor nem található.")
    valtozas = payload.model_dump(exclude_unset=True)
    for mezo, ertek in valtozas.items():
        setattr(m, mezo, ertek)
    # Ha az órát vagy az órabért írták át, de a fizetést nem, újraszámoljuk -
    # különben a sorban egy olyan bér maradna, ami már nem jön ki a saját
    # adataiból.
    if "fizetes" not in valtozas and ("ora" in valtozas or "orabar" in valtozas):
        if m.ora is not None and m.orabar is not None:
            m.fizetes = round(float(m.ora) * float(m.orabar), 2)
    db.commit()
    db.refresh(m)
    return _munkaora_kimenet(m)


class KifizetesJelolesIn(BaseModel):
    """Egy ember adott időszakának kifizetettre (vagy vissza) állítása.

    A kifizetés a gyakorlatban időszakonként történik: "Horváth Patrik,
    július 22. - augusztus 3., 455 550 Ft". Soronként kattintgatni ugyanezt
    tizennyolcszor kellene, és pont a végén, a legfáradtabb pillanatban
    maradna ki egy nap."""

    dolgozo_id: int
    tol: date | None = None
    ig: date | None = None
    kifizetve: bool = True
    #: Mikor történt a kifizetés. Üresen a mai nap - de átírható, mert a
    #: jelölés gyakran később készül el, mint maga az utalás.
    kifizetes_datuma: date | None = None


class KifizetesJelolesOut(BaseModel):
    #: Hány napot érintett a jelölés.
    erintett_napok: int
    #: Mennyi bér összege ez - a felület ezt írja vissza megerősítésként.
    osszeg: float


@router.post("/munkaorak/kifizetes", response_model=KifizetesJelolesOut)
def jelold_kifizetettnek(
    payload: KifizetesJelolesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy ember időszakának tömeges jelölése kifizetettként.

    CSAK a még nem jelölt napokat nyúlja (illetve visszavonásnál csak a
    jelölteket): így a kifizetés dátuma nem íródik felül egy korábbi,
    már elszámolt időszakon, ha valaki tágabb intervallumot ad meg."""
    if db.get(KrumpelloDolgozo, payload.dolgozo_id) is None:
        raise HTTPException(status_code=404, detail="Ez a dolgozó nem található.")
    stmt = select(KrumpelloMunkaora).where(
        KrumpelloMunkaora.dolgozo_id == payload.dolgozo_id,
        KrumpelloMunkaora.kifizetve.is_(not payload.kifizetve),
    )
    if payload.tol is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum >= payload.tol)
    if payload.ig is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum <= payload.ig)

    sorok = db.scalars(stmt).all()
    for m in sorok:
        m.kifizetve = payload.kifizetve
        m.kifizetes_datuma = (payload.kifizetes_datuma or date.today()) if payload.kifizetve else None
    db.commit()
    return KifizetesJelolesOut(
        erintett_napok=len(sorok),
        osszeg=sum(float(m.fizetes) if m.fizetes is not None else 0.0 for m in sorok),
    )


@router.delete("/munkaorak/{munkaora_id}", status_code=204)
def delete_munkaora(
    munkaora_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    m = db.get(KrumpelloMunkaora, munkaora_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Ez a munkaóra-sor nem található.")
    db.delete(m)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Összesítő
# ─────────────────────────────────────────────────────────────────────────────


class BevetelOut(BaseModel):
    brutto_kp: float
    brutto_kartya: float
    brutto: float
    netto_kp: float
    netto_kartya: float
    netto: float
    borravalo_kp: float
    borravalo_kartya: float
    borravalo: float
    extra: float


class KiadasBontasOut(BaseModel):
    netto: float
    afa: float
    brutto: float


class OsszesitoOut(BaseModel):
    bevetel: BevetelOut
    kiadas_utalas: KiadasBontasOut
    kiadas_keszpenz: KiadasBontasOut
    kiadas_extra: float
    szamla_egyenleg_netto: float
    szamla_egyenleg_brutto: float
    keszpenz_egyenleg_netto: float
    keszpenz_egyenleg_brutto: float
    extra_bevetel: float
    extra_egyenleg: float
    munkaora: float
    munkaber: float
    munkaber_borravalo: float
    munkaber_hatralek: float


@router.get("/osszesito", response_model=OsszesitoOut)
def get_osszesito(
    tol: date | None = None,
    ig: date | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    """A kassza-táblázat ÖSSZESÍTŐ blokkja - lásd
    services/krumpello_osszesito.py, ott van leírva, mit mér a három egyenleg."""
    o = krumpello_osszesito.osszesito(db, tol, ig)
    ures = krumpello_osszesito.KiadasBontas()
    utalas = o.kiadas.get("utalas", ures)
    keszpenz = o.kiadas.get("keszpenz", ures)
    return OsszesitoOut(
        bevetel=BevetelOut(
            brutto_kp=o.bevetel.brutto_kp,
            brutto_kartya=o.bevetel.brutto_kartya,
            brutto=o.bevetel.brutto,
            netto_kp=o.bevetel.netto_kp,
            netto_kartya=o.bevetel.netto_kartya,
            netto=o.bevetel.netto,
            borravalo_kp=o.bevetel.borravalo_kp,
            borravalo_kartya=o.bevetel.borravalo_kartya,
            borravalo=o.bevetel.borravalo,
            extra=o.bevetel.extra,
        ),
        kiadas_utalas=KiadasBontasOut(netto=utalas.netto, afa=utalas.afa, brutto=utalas.brutto),
        kiadas_keszpenz=KiadasBontasOut(netto=keszpenz.netto, afa=keszpenz.afa, brutto=keszpenz.brutto),
        kiadas_extra=o.extra_kiadas,
        szamla_egyenleg_netto=o.szamla_egyenleg_netto,
        szamla_egyenleg_brutto=o.szamla_egyenleg_brutto,
        keszpenz_egyenleg_netto=o.keszpenz_egyenleg_netto,
        keszpenz_egyenleg_brutto=o.keszpenz_egyenleg_brutto,
        extra_bevetel=o.extra_bevetel,
        extra_egyenleg=o.extra_egyenleg,
        munkaora=o.munkaora,
        munkaber=o.munkaber,
        munkaber_borravalo=o.munkaber_borravalo,
        munkaber_hatralek=o.munkaber_hatralek,
    )


class HozzaferesOut(BaseModel):
    """Látja-e a bejelentkezett ember a Krumpellót?

    A HYPE OS fejlécében ülő kapcsoló ezt kérdezi meg - jog nélkül a kapcsoló
    meg sem jelenik, tehát nem is derül ki belőle, hogy létezik ez a rész."""

    van_hozzaferes: bool


@router.get("/hozzaferes", response_model=HozzaferesOut)
def get_hozzaferes(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)):
    return HozzaferesOut(van_hozzaferes=lathatja(db, user))
