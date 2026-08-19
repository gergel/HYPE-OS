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
    ALAP_BEJELENTES,
    BEJELENTES_CIMKEK,
    BEJELENTESEK,
    KIADAS_FORRASOK,
    KrumpelloDolgozo,
    KrumpelloKiadas,
    KrumpelloIdoszak,
    KrumpelloMunkaora,
    KrumpelloNap,
)
from app.models.document_attachment import DocumentAttachment
from app.models.user_access import PageAccessConfig
from app.schemas.document_attachment import DocumentAttachmentRead
from app.services import attachments, krumpello_munkaber, krumpello_osszesito

router = APIRouter(prefix="/krumpello", tags=["krumpello"])

PAGE = "/krumpello"

#: A csatolmányok entitás-kulcsai (lásd services/entity_registry.py). Minden
#: tételhez tölthető fel számla/blokk, de EGYIKHEZ SEM kötelező: az "extra"
#: forrásnak épp az a definíciója, hogy nincs mögötte papír.
KIADAS_ENTITAS = "krumpelloKiadas"
NAP_ENTITAS = "krumpelloNap"


def _csatolmanyok(db: Session, entitas: str, idk: list[int]) -> dict[int, list[DocumentAttachmentRead]]:
    """A tételekhez tartozó fájlok, EGY lekérdezéssel.

    Szándékosan itt, a listával együtt: soronként lekérdezve egy hónapnyi
    kassza megnyitása több tucat kérést indítana olyan sorokhoz is, ahol nincs
    is fájl."""
    if not idk:
        return {}
    sorok = db.scalars(
        select(DocumentAttachment)
        .where(DocumentAttachment.entity_type == entitas, DocumentAttachment.entity_id.in_(idk))
        .order_by(DocumentAttachment.id)
    ).all()
    eredmeny: dict[int, list[DocumentAttachmentRead]] = {}
    for sor in sorok:
        eredmeny.setdefault(sor.entity_id, []).append(DocumentAttachmentRead.model_validate(sor))
    return eredmeny


def _dobd_el_a_fajlokat(db: Session, entitas: str, entity_id: int) -> None:
    """A törölt tétel fájljai is menjenek - a tárhelyről is.

    Enélkül a feltöltött blokk örökre ott maradna az R2-n, egy olyan tételre
    hivatkozva, ami már nincs: senki nem látná, és senki nem tudná törölni."""
    for sor in attachments.list_for(db, entitas, entity_id):
        attachments.delete(db, sor)


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
    #: A naphoz feltöltött számlák/blokkok. Nem kötelező - lehet üres.
    csatolmanyok: list[DocumentAttachmentRead] = []


def _nap_kimenet(nap: KrumpelloNap, csatolmanyok: list[DocumentAttachmentRead] | None = None) -> NapRead:
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
        csatolmanyok=csatolmanyok or [],
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
    napok = db.scalars(stmt.order_by(KrumpelloNap.datum.desc())).all()
    fajlok = _csatolmanyok(db, NAP_ENTITAS, [n.id for n in napok])
    return [_nap_kimenet(n, fajlok.get(n.id)) for n in napok]


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
    _dobd_el_a_fajlokat(db, NAP_ENTITAS, nap.id)
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
    #: A tételhez feltöltött számlák/blokkok. Nem kötelező - lehet üres.
    csatolmanyok: list[DocumentAttachmentRead] = []


def _ellenorzott_forras(forras: str) -> str:
    if forras not in KIADAS_FORRASOK:
        raise HTTPException(
            status_code=400,
            detail=f"Ismeretlen forrás. Választható: {', '.join(KIADAS_FORRASOK)}",
        )
    return forras


def _kiadas_kimenet(k: KrumpelloKiadas, csatolmanyok: list[DocumentAttachmentRead] | None = None) -> KiadasRead:
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
        csatolmanyok=csatolmanyok or [],
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
    fajlok = _csatolmanyok(db, KIADAS_ENTITAS, [k.id for k in sorok])
    return [_kiadas_kimenet(k, fajlok.get(k.id)) for k in sorok]


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
    _dobd_el_a_fajlokat(db, KIADAS_ENTITAS, k.id)
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
    #: Üresen hagyva az időszakából örökli (lásd services/krumpello_munkaber.py).
    bejelentes: str | None = None
    bejelentett_napi_ber: float | None = None


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
    bejelentes: str | None = None
    bejelentett_napi_ber: float | None = None


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

    #: A NAPRA beírt saját érték (üres = az időszakból örökli).
    bejelentes: str | None = None
    bejelentett_napi_ber: float | None = None
    #: A ténylegesen érvényes bejelentés és a belőle következő pénzbontás
    #: (lásd services/krumpello_munkaber.py). A felület ezt írja ki: az
    #: örökölt értéket ugyanúgy látni kell, mint a kézzel megadottat.
    ervenyes_bejelentes: str = ALAP_BEJELENTES
    bejelentes_forrasa: str = "idoszak"
    idoszak_id: int | None = None
    utalando: float = 0.0
    keszpenz: float = 0.0


def _ellenorizd_a_bejelentest(ertek: str | None) -> None:
    """A bejelentés zárt értékkészlet: ami ide bekerül, abból elszámolás lesz.

    Az üres érték megengedett: az azt jelenti, hogy a nap az IDŐSZAKÁBÓL
    örökli a bejelentést (lásd services/krumpello_munkaber.py)."""
    if ertek is not None and ertek not in BEJELENTESEK:
        raise HTTPException(
            status_code=400, detail=f"Ismeretlen bejelentés. Választható: {', '.join(BEJELENTESEK)}"
        )


def _szamolt_fizetes(payload: MunkaoraIn) -> float | None:
    """A napra járó bér. A beküldött érték mindig erősebb: a kerekítés, a
    megbeszélt átalány és a pótlék így nem tűnik el egy automatizmus miatt
    (lásd models/krumpello.py KrumpelloMunkaora)."""
    if payload.fizetes is not None:
        return payload.fizetes
    if payload.ora is not None and payload.orabar is not None:
        return round(payload.ora * payload.orabar, 2)
    return None


def _munkaora_kimenet(m: KrumpelloMunkaora, idoszakok: list[KrumpelloIdoszak] | None = None) -> MunkaoraRead:
    """Egy munkanap kimenete, a bejelentésből következő pénzbontással együtt.

    Az `idoszakok` azért paraméter, mert a listánál EGYSZER kérjük le
    dolgozónként - soronként újralekérdezve több száz sornál ugyanannyi
    fölösleges kör lenne."""
    bontas = krumpello_munkaber.bontsd_a_napot(m, idoszakok or [])
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
        bejelentes=m.bejelentes,
        bejelentett_napi_ber=_f(m.bejelentett_napi_ber),
        ervenyes_bejelentes=bontas.bejelentes,
        bejelentes_forrasa=bontas.bejelentes_forrasa,
        idoszak_id=bontas.idoszak_id,
        utalando=bontas.utalando,
        keszpenz=bontas.keszpenz,
    )


def _idoszak_terkep(db: Session, dolgozo_idk: set[int]) -> dict[int, list[KrumpelloIdoszak]]:
    """Dolgozónként az időszakai - EGY lekérdezésből."""
    if not dolgozo_idk:
        return {}
    terkep: dict[int, list[KrumpelloIdoszak]] = {}
    for i in db.scalars(
        select(KrumpelloIdoszak)
        .where(KrumpelloIdoszak.dolgozo_id.in_(dolgozo_idk))
        .order_by(KrumpelloIdoszak.kezdet)
    ):
        terkep.setdefault(i.dolgozo_id, []).append(i)
    return terkep


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
    terkep = _idoszak_terkep(db, {m.dolgozo_id for m in sorok})
    return [_munkaora_kimenet(m, terkep.get(m.dolgozo_id, [])) for m in sorok]


@router.post("/munkaorak", response_model=MunkaoraRead, status_code=201)
def create_munkaora(
    payload: MunkaoraIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    dolgozo = db.get(KrumpelloDolgozo, payload.dolgozo_id)
    if dolgozo is None:
        raise HTTPException(status_code=404, detail="Ez a dolgozó nem található.")
    _ellenorizd_a_bejelentest(payload.bejelentes)
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
    return _munkaora_kimenet(m, krumpello_munkaber.dolgozo_idoszakai(db, m.dolgozo_id))


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
    if "bejelentes" in valtozas:
        _ellenorizd_a_bejelentest(valtozas["bejelentes"])
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
    return _munkaora_kimenet(m, krumpello_munkaber.dolgozo_idoszakai(db, m.dolgozo_id))


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


# ─────────────────────────────────────────────────────────────────────────────
# Foglalkoztatási időszakok és elszámolás
# ─────────────────────────────────────────────────────────────────────────────


class IdoszakIn(BaseModel):
    dolgozo_id: int
    kezdet: date
    #: Üresen: azóta is tart.
    veg: date | None = None
    bejelentes: str = ALAP_BEJELENTES
    napi_ber: float | None = None
    nev: str | None = None
    megjegyzes: str | None = None


class IdoszakPatch(BaseModel):
    """Részleges módosítás. A dolgozó nincs benne: egy időszakot nem lehet
    átrakni másik emberre - az valójában "rossz helyre vittem fel", amire a
    törlés és az újrafelvitel a helyes út."""

    kezdet: date | None = None
    veg: date | None = None
    bejelentes: str | None = None
    napi_ber: float | None = None
    nev: str | None = None
    megjegyzes: str | None = None


class IdoszakRead(BaseModel):
    id: int
    dolgozo_id: int
    dolgozo_nev: str
    kezdet: date
    veg: date | None = None
    bejelentes: str
    bejelentes_cimke: str
    napi_ber: float | None = None
    nev: str | None = None
    megjegyzes: str | None = None

    #: Az időszak elszámolása - ezért van egyáltalán ez a nézet.
    napok_szama: int = 0
    ora_osszesen: float = 0.0
    jarandosag: float = 0.0
    utalando: float = 0.0
    keszpenz: float = 0.0
    borravalo: float = 0.0
    kifizetett: float = 0.0
    hatralek: float = 0.0
    kifizetett_napok: int = 0
    teljesen_kifizetve: bool = False


class IdoszakNap(BaseModel):
    """Egy nap az időszak részletes bontásában."""

    munkaora_id: int
    datum: date
    ora: float = 0.0
    orabar: float = 0.0
    jarandosag: float = 0.0
    borravalo: float = 0.0
    bejelentes: str
    bejelentes_cimke: str
    bejelentes_forrasa: str
    utalando: float = 0.0
    keszpenz: float = 0.0
    #: A bejelentett bér többet fizet, mint amennyi aznap járt (rövid nap).
    tulfizetett: bool = False
    kifizetve: bool = False
    kifizetes_datuma: date | None = None


class IdoszakReszletek(IdoszakRead):
    napok: list[IdoszakNap] = []


def _idoszak_kimenet(i: KrumpelloIdoszak, e: krumpello_munkaber.Elszamolas) -> IdoszakRead:
    return IdoszakRead(
        id=i.id,
        dolgozo_id=i.dolgozo_id,
        dolgozo_nev=i.dolgozo.nev if i.dolgozo else f"#{i.dolgozo_id}",
        kezdet=i.kezdet,
        veg=i.veg,
        bejelentes=i.bejelentes,
        bejelentes_cimke=BEJELENTES_CIMKEK.get(i.bejelentes, i.bejelentes),
        napi_ber=_f(i.napi_ber),
        nev=i.nev,
        megjegyzes=i.megjegyzes,
        napok_szama=e.napok_szama,
        ora_osszesen=e.ora_osszesen,
        jarandosag=e.jarandosag,
        utalando=e.utalando,
        keszpenz=e.keszpenz,
        borravalo=e.borravalo,
        kifizetett=e.kifizetett,
        hatralek=e.hatralek,
        kifizetett_napok=e.kifizetett_napok,
        teljesen_kifizetve=e.teljesen_kifizetve,
    )


def _idoszak_vagy_404(db: Session, idoszak_id: int) -> KrumpelloIdoszak:
    i = db.get(KrumpelloIdoszak, idoszak_id)
    if i is None:
        raise HTTPException(status_code=404, detail="Ez az időszak nem található.")
    return i


def _ellenorizd_az_idoszakot(
    db: Session, dolgozo_id: int, kezdet: date, veg: date | None, kihagyott_id: int | None = None
) -> None:
    """Érvényes-e az időszak? Két dolgot nézünk, és mindkettő némán rossz
    elszámolást okozna: a fordított dátumpárt, és az ütközést."""
    if veg is not None and veg < kezdet:
        raise HTTPException(status_code=400, detail="Az időszak vége nem lehet a kezdete előtt.")
    utkozo = krumpello_munkaber.atfedes(
        krumpello_munkaber.dolgozo_idoszakai(db, dolgozo_id), kezdet, veg, kihagyott_id
    )
    if utkozo is not None:
        vege = utkozo.veg.isoformat() if utkozo.veg else "nyitott"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ütközik egy meglévő időszakkal ({utkozo.kezdet.isoformat()} - {vege}). "
                "Egy napra csak egy bejelentés tartozhat, ezért az időszakok nem fedhetik egymást."
            ),
        )


@router.get("/idoszakok", response_model=list[IdoszakRead])
def list_idoszakok(
    dolgozo_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    """A foglalkoztatási időszakok, mindegyik a saját elszámolásával."""
    stmt = select(KrumpelloIdoszak)
    if dolgozo_id is not None:
        stmt = stmt.where(KrumpelloIdoszak.dolgozo_id == dolgozo_id)
    sorok = db.scalars(stmt.order_by(KrumpelloIdoszak.kezdet.desc(), KrumpelloIdoszak.id.desc())).all()
    return [_idoszak_kimenet(i, krumpello_munkaber.idoszak_elszamolasa(db, i)) for i in sorok]


@router.get("/idoszakok/{idoszak_id}", response_model=IdoszakReszletek)
def get_idoszak(
    idoszak_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(olvashat),
):
    """Egy időszak elszámolása NAPI BONTÁSSAL - ebből látszik, melyik napból
    mennyi megy utalással és mennyi készpénzben."""
    i = _idoszak_vagy_404(db, idoszak_id)
    e = krumpello_munkaber.idoszak_elszamolasa(db, i)
    alap = _idoszak_kimenet(i, e)
    return IdoszakReszletek(
        **alap.model_dump(),
        napok=[
            IdoszakNap(
                munkaora_id=b.munkaora_id,
                datum=b.datum,
                ora=b.ora,
                orabar=b.orabar,
                jarandosag=b.jarandosag,
                borravalo=b.borravalo,
                bejelentes=b.bejelentes,
                bejelentes_cimke=b.bejelentes_cimke,
                bejelentes_forrasa=b.bejelentes_forrasa,
                utalando=b.utalando,
                keszpenz=b.keszpenz,
                tulfizetett=b.tulfizetett,
                kifizetve=b.kifizetve,
                kifizetes_datuma=b.kifizetes_datuma,
            )
            for b in e.bontasok
        ],
    )


@router.post("/idoszakok", response_model=IdoszakRead, status_code=201)
def create_idoszak(
    payload: IdoszakIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    if db.get(KrumpelloDolgozo, payload.dolgozo_id) is None:
        raise HTTPException(status_code=404, detail="Ez a dolgozó nem található.")
    if payload.bejelentes not in BEJELENTESEK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen bejelentés. Választható: {', '.join(BEJELENTESEK)}")
    _ellenorizd_az_idoszakot(db, payload.dolgozo_id, payload.kezdet, payload.veg)
    i = KrumpelloIdoszak(**payload.model_dump())
    db.add(i)
    db.commit()
    db.refresh(i)
    return _idoszak_kimenet(i, krumpello_munkaber.idoszak_elszamolasa(db, i))


@router.patch("/idoszakok/{idoszak_id}", response_model=IdoszakRead)
def update_idoszak(
    idoszak_id: int,
    payload: IdoszakPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    i = _idoszak_vagy_404(db, idoszak_id)
    adat = payload.model_dump(exclude_unset=True)
    if "bejelentes" in adat and adat["bejelentes"] not in BEJELENTESEK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen bejelentés. Választható: {', '.join(BEJELENTESEK)}")
    # A dátumokat a MOSTANI értékekkel együtt kell nézni: egy PATCH tipikusan
    # csak az egyik végét küldi el.
    _ellenorizd_az_idoszakot(
        db,
        i.dolgozo_id,
        adat.get("kezdet", i.kezdet),
        adat.get("veg", i.veg),
        kihagyott_id=i.id,
    )
    for mezo, ertek in adat.items():
        setattr(i, mezo, ertek)
    db.commit()
    db.refresh(i)
    return _idoszak_kimenet(i, krumpello_munkaber.idoszak_elszamolasa(db, i))


@router.delete("/idoszakok/{idoszak_id}", status_code=204)
def delete_idoszak(
    idoszak_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Az időszak törlése a MUNKANAPOKAT nem viszi el.

    Csak a bejelentés esik le róluk (visszaesnek "nem volt bejelentve"-re,
    hacsak a napon nincs saját érték) - a ledolgozott óra és a bér megmarad.
    Így egy elrontott időszak javítható anélkül, hogy elszámolt munkanapok
    tűnnének el."""
    db.delete(_idoszak_vagy_404(db, idoszak_id))
    db.commit()


class IdoszakElszamolasIn(BaseModel):
    """Egy vagy TÖBB időszak elszámolása egyben.

    Több azért, mert a kifizetés a gyakorlatban nem mindig egy időszakra szól:
    ha valakinél egy EFO-s és egy szerződéses szakasz is nyitva maradt, egyszerre
    rendezik őket - és a felhasználó egy összeget ad oda, nem kettőt."""

    idoszak_idk: list[int]
    kifizetve: bool = True
    kifizetes_datuma: date | None = None


class IdoszakElszamolasOut(BaseModel):
    erintett_napok: int
    #: A teljes járandóság, és a bontása - ennyit kell utalni, ennyit kp-ban adni.
    jarandosag: float
    utalando: float
    keszpenz: float


@router.post("/idoszakok/elszamolas", response_model=IdoszakElszamolasOut)
def szamold_el_az_idoszakokat(
    payload: IdoszakElszamolasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Időszak(ok) kifizetettre jelölése, a bontás visszaadásával.

    CSAK a még nem jelölt napokat nyúlja (visszavonásnál csak a jelölteket) -
    ugyanaz az elv, mint a napi jelölésnél: egy tágabb elszámolás ne írja felül
    egy korábbi kifizetés dátumát.

    A válasz megmondja, MENNYIT kell utalni és mennyit készpénzben odaadni -
    ez az a két szám, amivel a felhasználó a bankhoz és a kasszához megy."""
    napok: list[KrumpelloMunkaora] = []
    bontasok: list[krumpello_munkaber.NapiBontas] = []
    for idoszak_id in payload.idoszak_idk:
        i = _idoszak_vagy_404(db, idoszak_id)
        idoszakok = krumpello_munkaber.dolgozo_idoszakai(db, i.dolgozo_id)
        for m in krumpello_munkaber.idoszak_napjai(db, i):
            if m.kifizetve == payload.kifizetve or m.id in {n.id for n in napok}:
                continue
            napok.append(m)
            bontasok.append(krumpello_munkaber.bontsd_a_napot(m, idoszakok))

    for m in napok:
        m.kifizetve = payload.kifizetve
        m.kifizetes_datuma = (payload.kifizetes_datuma or date.today()) if payload.kifizetve else None
    db.commit()

    e = krumpello_munkaber.szamold_ki(bontasok)
    return IdoszakElszamolasOut(
        erintett_napok=len(napok),
        jarandosag=e.jarandosag,
        utalando=e.utalando,
        keszpenz=e.keszpenz,
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
