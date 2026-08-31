"""Visszatérő kötelezettségek: előfizetések (E-Rezsi), biztosítások, autók
papírjai - és a hozzájuk tartozó fordulónkénti összeg + számla.

Egy router szolgálja ki mindhárom felületet, mert a viselkedésük azonos: van
egy forduló, arra készül egy időszak, abba be kell írni a ténylegesen levont
összeget és fel kell tölteni a számlát. Ami elválik, az csak a szűrés (`tipus`,
`auto_id`) és az, hogy melyik oldal jogosultsága kell hozzá.

A lejáratra figyelmeztetés nem külön kapcsoló: a lista lekérésekor fut le az
időszakok és a feladatok "utolérése" (lásd services/kotelezettseg.py) - ütemező
nincs a rendszerben, ezért minden ilyen művelet igény szerint, idempotensen
történik."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_page_action
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.schemas.document_attachment import DocumentAttachmentRead
from app.models.kotelezettseg import (
    Kotelezettseg,
    KotelezettsegCiklus,
    KotelezettsegIdoszak,
    KotelezettsegTipus,
)
from app.services import kotelezettseg as szolg
from app.services import kotelezettseg_import

router = APIRouter(prefix="/kotelezettsegek", tags=["kotelezettsegek"])

PAGE = "/kotelezettsegek"

#: A durva admin/operator szerepkör-kapu itt nem érvényes: akinek admin a
#: Beállításokban jogot adott erre az oldalra, az a szerepkörétől
#: függetlenül dolgozhat rajta (ugyanaz az elv, mint az Utómunkánál -
#: lásd routes/postproduction.py _MINDEN_SZEREPKOR). A page_permissions
#: védelem változatlanul él.
_MINDEN_SZEREPKOR = tuple(Role)

#: A csatolmányok entity_type-jai (lásd services/attachments.py):
#: az EGY FORDULÓHOZ tartozó számla, és a kötelezettséghez MAGÁHOZ tartozó
#: papír (kötvény, szerződés, forgalmi másolat) - utóbbi nem egy fizetéshez,
#: hanem az egészhez tartozik, ezért nem fér el az időszakon.
CSATOLMANY_ENTITAS = "kotelezettsegIdoszak"
PAPIR_ENTITAS = "kotelezettseg"

CIKLUSOK = [c.value for c in KotelezettsegCiklus]
TIPUSOK = [t.value for t in KotelezettsegTipus]


# ─────────────────────────────────────────────────────────────────────────────
# Kimenő alakok
# ─────────────────────────────────────────────────────────────────────────────


class IdoszakRead(BaseModel):
    id: int
    kotelezettseg_id: int
    esedekesseg: date
    #: A ténylegesen levont összeg NETTÓBAN.
    osszeg: float | None = None
    plusz_afa: bool = False
    #: A nettóból és az áfa-jelölésből számolva - nem tárolt mező, hogy a
    #: kettő sose mondhasson ellent egymásnak.
    brutto: float | None = None
    penznem: str = "HUF"
    huf_osszeg: float | None = None
    fizetve: bool = False
    megjegyzes: str | None = None
    #: Hány számla van feltöltve ehhez a fordulóhoz.
    szamla_db: int = 0
    #: MAGUK a feltöltött számlák - enélkül a felület csak a darabszámot tudta
    #: kiírni, a fájlt megnyitni vagy törölni nem lehetett. A lista ugyanabból
    #: a lekérdezésből jön, amiből a darabszám (lásd _szamlak), tehát nem kerül
    #: plusz adatbázis-fordulóba.
    szamlak: list[DocumentAttachmentRead] = []
    #: Mi hiányzik még ("Összeg nincs beírva" / "Számla hiányzik"), None = kész.
    hianyzik: str | None = None


class KotelezettsegRead(BaseModel):
    id: int
    nev: str
    csomag: str | None = None
    tipus: str
    ciklus: str
    fordulo_nap: int | None = None
    fordulo_honap: int | None = None
    kovetkezo_fordulo: date | None = None
    kezdet: date | None = None
    osztaly: str | None = None
    felelos_id: int | None = None
    felelos_nev: str | None = None
    auto_id: int | None = None
    aktiv: bool = True
    fizetesi_mod: str | None = None
    #: Nettó ár ciklusonként; a bruttó ebből és az áfa-jelölésből számolódik.
    ar_osszeg: float | None = None
    ar_plusz_afa: bool = False
    ar_brutto: float | None = None
    ar_penznem: str = "HUF"
    huf_becsles_honap: float | None = None
    huf_becsles_ev: float | None = None
    szamla_forras: str | None = None
    kartya: str | None = None
    megjegyzes: str | None = None
    ertesites_napokkal: int = 14

    #: A számított rész - ezt nem tárolja senki, minden lekérésnél a mai
    #: naphoz képest áll elő (lásd services/kotelezettseg.py).
    kovetkezo_esedekesseg: date | None = None
    napok_hatra: int | None = None
    #: inaktiv | lejart | hamarosan | rendben | nincs_datum
    allapot: str = "rendben"
    #: Hány esedékes fordulónál hiányzik még az összeg vagy a számla.
    nyitott_idoszakok: int = 0
    #: Hány papír (kötvény, szerződés) van feltöltve magához a kötelezettséghez.
    papir_db: int = 0
    idoszakok: list[IdoszakRead] = []


#: A magyar általános áfakulcs. Egy helyen áll, hogy a nettó -> bruttó
#: átváltás mindenhol ugyanaz legyen.
AFA_SZORZO = 1.27


def brutto(netto: float | None, plusz_afa: bool) -> float | None:
    """Bruttó a nettóból. Ha nincs áfa, a kettő ugyanaz."""
    if netto is None:
        return None
    return round(netto * AFA_SZORZO, 2) if plusz_afa else float(netto)


def _szamlak(db: Session, idoszak_idk: list[int]) -> dict[int, list[DocumentAttachment]]:
    """Fordulónként a feltöltött számlák. Egy lekérdezés az egész listához."""
    if not idoszak_idk:
        return {}
    sorok = db.scalars(
        select(DocumentAttachment).where(
            DocumentAttachment.entity_type == CSATOLMANY_ENTITAS,
            DocumentAttachment.entity_id.in_(idoszak_idk),
        )
    ).all()
    szerint: dict[int, list[DocumentAttachment]] = {}
    for sor in sorok:
        szerint.setdefault(sor.entity_id, []).append(sor)
    return szerint


def _papir_db(db: Session, kotelezettseg_idk: list[int]) -> dict[int, int]:
    """Hány papír tartozik magukhoz a kötelezettségekhez (nem a fordulóikhoz)."""
    if not kotelezettseg_idk:
        return {}
    sorok = db.scalars(
        select(DocumentAttachment).where(
            DocumentAttachment.entity_type == PAPIR_ENTITAS,
            DocumentAttachment.entity_id.in_(kotelezettseg_idk),
        )
    ).all()
    darab: dict[int, int] = {}
    for sor in sorok:
        darab[sor.entity_id] = darab.get(sor.entity_id, 0) + 1
    return darab


def _kimenet(
    k: Kotelezettseg,
    darab: dict[int, list[DocumentAttachment]],
    ma: date,
    papirok: dict[int, int] | None = None,
) -> KotelezettsegRead:
    idoszakok = [
        IdoszakRead(
            id=i.id,
            kotelezettseg_id=i.kotelezettseg_id,
            esedekesseg=i.esedekesseg,
            osszeg=float(i.osszeg) if i.osszeg is not None else None,
            plusz_afa=bool(i.plusz_afa),
            brutto=brutto(float(i.osszeg) if i.osszeg is not None else None, bool(i.plusz_afa)),
            penznem=i.penznem,
            huf_osszeg=float(i.huf_osszeg) if i.huf_osszeg is not None else None,
            fizetve=i.fizetve,
            megjegyzes=i.megjegyzes,
            szamla_db=len(darab.get(i.id, [])),
            szamlak=[DocumentAttachmentRead.model_validate(f) for f in darab.get(i.id, [])],
            hianyzik=szolg.hianyzo_teendo(i, bool(darab.get(i.id))),
        )
        for i in sorted(k.idoszakok, key=lambda i: i.esedekesseg, reverse=True)
    ]
    return KotelezettsegRead(
        id=k.id,
        nev=k.nev,
        csomag=k.csomag,
        tipus=k.tipus,
        ciklus=k.ciklus,
        fordulo_nap=k.fordulo_nap,
        fordulo_honap=k.fordulo_honap,
        kovetkezo_fordulo=k.kovetkezo_fordulo,
        kezdet=k.kezdet,
        osztaly=k.osztaly,
        felelos_id=k.felelos_id,
        felelos_nev=k.felelos.full_name if k.felelos else None,
        auto_id=k.auto_id,
        aktiv=k.aktiv,
        fizetesi_mod=k.fizetesi_mod,
        ar_osszeg=float(k.ar_osszeg) if k.ar_osszeg is not None else None,
        ar_plusz_afa=bool(k.ar_plusz_afa),
        ar_brutto=brutto(float(k.ar_osszeg) if k.ar_osszeg is not None else None, bool(k.ar_plusz_afa)),
        ar_penznem=k.ar_penznem,
        huf_becsles_honap=float(k.huf_becsles_honap) if k.huf_becsles_honap is not None else None,
        huf_becsles_ev=float(k.huf_becsles_ev) if k.huf_becsles_ev is not None else None,
        szamla_forras=k.szamla_forras,
        kartya=k.kartya,
        megjegyzes=k.megjegyzes,
        ertesites_napokkal=k.ertesites_napokkal,
        kovetkezo_esedekesseg=szolg.kovetkezo_esedekesseg(k, ma),
        napok_hatra=szolg.hatralevo_napok(k, ma),
        allapot=szolg.allapot(k, ma),
        nyitott_idoszakok=sum(1 for i in idoszakok if i.hianyzik is not None),
        papir_db=(papirok or {}).get(k.id, 0),
        idoszakok=idoszakok,
    )


def _betolt(db: Session) -> list[Kotelezettseg]:
    return list(
        db.scalars(
            select(Kotelezettseg)
            .options(selectinload(Kotelezettseg.idoszakok), selectinload(Kotelezettseg.felelos))
            .order_by(Kotelezettseg.nev)
        ).all()
    )


@router.get("", response_model=list[KotelezettsegRead])
def list_kotelezettsegek(
    tipus: str | None = None,
    auto_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """A kötelezettségek a számított állapotukkal és az esedékes időszakaikkal.

    A `tipus` szűri az oldalakat: az E-Rezsi az "elofizetes" sorokat mutatja, a
    Biztosítások oldal a többit, az autó lapja pedig az `auto_id`-ra szűr.

    A lekérés MELLÉKHATÁSA, hogy létrejönnek a hiányzó időszakok és a közelgő
    fordulók feladatai - ez az "értesít, amikor lejár" működés motorja
    (lásd services/kotelezettseg.py)."""
    szolg.ensure_mindent(db)
    ma = date.today()
    sorok = _betolt(db)
    if tipus:
        kertek = {t.strip() for t in tipus.split(",") if t.strip()}
        sorok = [k for k in sorok if k.tipus in kertek]
    if auto_id is not None:
        sorok = [k for k in sorok if k.auto_id == auto_id]
    darab = _szamlak(db, [i.id for k in sorok for i in k.idoszakok])
    papirok = _papir_db(db, [k.id for k in sorok])
    return [_kimenet(k, darab, ma, papirok) for k in sorok]


@router.get("/{kotelezettseg_id}", response_model=KotelezettsegRead)
def get_kotelezettseg(
    kotelezettseg_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    k = db.get(Kotelezettseg, kotelezettseg_id)
    if k is None:
        raise HTTPException(status_code=404, detail="A kötelezettség nem található.")
    darab = _szamlak(db, [i.id for i in k.idoszakok])
    return _kimenet(k, darab, date.today(), _papir_db(db, [k.id]))


# ─────────────────────────────────────────────────────────────────────────────
# Szerkesztés
# ─────────────────────────────────────────────────────────────────────────────


class KotelezettsegIn(BaseModel):
    nev: str
    csomag: str | None = None
    tipus: str = KotelezettsegTipus.ELOFIZETES.value
    ciklus: str = KotelezettsegCiklus.HAVI.value
    fordulo_nap: int | None = None
    fordulo_honap: int | None = None
    kovetkezo_fordulo: date | None = None
    kezdet: date | None = None
    osztaly: str | None = None
    felelos_id: int | None = None
    auto_id: int | None = None
    aktiv: bool = True
    fizetesi_mod: str | None = None
    #: Nettó ár ciklusonként; a bruttó ebből és az áfa-jelölésből számolódik.
    ar_osszeg: float | None = None
    ar_plusz_afa: bool = False
    ar_penznem: str = "HUF"
    huf_becsles_honap: float | None = None
    huf_becsles_ev: float | None = None
    szamla_forras: str | None = None
    kartya: str | None = None
    megjegyzes: str | None = None
    ertesites_napokkal: int = 14


def _ellenoriz(payload: KotelezettsegIn) -> None:
    if not payload.nev.strip():
        raise HTTPException(status_code=400, detail="A megnevezés kötelező.")
    if payload.tipus not in TIPUSOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen típus. Választható: {', '.join(TIPUSOK)}")
    if payload.ciklus not in CIKLUSOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen ciklus. Választható: {', '.join(CIKLUSOK)}")
    if payload.fordulo_nap is not None and not 1 <= payload.fordulo_nap <= 31:
        raise HTTPException(status_code=400, detail="A forduló napja 1 és 31 közé eshet.")
    if payload.fordulo_honap is not None and not 1 <= payload.fordulo_honap <= 12:
        raise HTTPException(status_code=400, detail="A forduló hónapja 1 és 12 közé eshet.")
    # Enélkül a kötelezettség némán "nincs dátum" állapotban ülne a listán, és
    # sosem szólna a lejáratáról - pont az veszne el, amiért felvitték.
    if payload.kovetkezo_fordulo is None and payload.fordulo_nap is None:
        raise HTTPException(status_code=400, detail="Add meg a következő forduló (lejárat) dátumát.")
    if (
        payload.ciklus == KotelezettsegCiklus.EVES
        and payload.kovetkezo_fordulo is None
        and payload.fordulo_honap is None
    ):
        # Csak a Google-táblázatból importált, dátum nélküli soroknál fordulhat
        # elő: ott a minta az egyetlen forrás, és éveshez a hónap is kell.
        raise HTTPException(status_code=400, detail="Éves ciklusnál a forduló hónapját is meg kell adni.")


@router.post("", response_model=KotelezettsegRead, status_code=201)
def create_kotelezettseg(
    payload: KotelezettsegIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    _ellenoriz(payload)
    k = Kotelezettseg(**payload.model_dump())
    k.nev = k.nev.strip()
    db.add(k)
    db.commit()
    db.refresh(k)
    szolg.ensure_mindent(db)
    db.refresh(k)
    return _kimenet(k, _szamlak(db, [i.id for i in k.idoszakok]), date.today(), _papir_db(db, [k.id]))


@router.put("/{kotelezettseg_id}", response_model=KotelezettsegRead)
def update_kotelezettseg(
    kotelezettseg_id: int,
    payload: KotelezettsegIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    k = db.get(Kotelezettseg, kotelezettseg_id)
    if k is None:
        raise HTTPException(status_code=404, detail="A kötelezettség nem található.")
    _ellenoriz(payload)
    for mezo, ertek in payload.model_dump().items():
        setattr(k, mezo, ertek)
    k.nev = k.nev.strip()
    db.commit()
    szolg.ensure_mindent(db)
    db.refresh(k)
    return _kimenet(k, _szamlak(db, [i.id for i in k.idoszakok]), date.today(), _papir_db(db, [k.id]))


@router.delete("/{kotelezettseg_id}", status_code=204)
def delete_kotelezettseg(
    kotelezettseg_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    k = db.get(Kotelezettseg, kotelezettseg_id)
    if k is None:
        raise HTTPException(status_code=404, detail="A kötelezettség nem található.")
    db.delete(k)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Időszakok: "pontosan mennyibe került"
# ─────────────────────────────────────────────────────────────────────────────


class IdoszakIn(BaseModel):
    #: NETTÓ összeg.
    osszeg: float | None = None
    plusz_afa: bool | None = None
    penznem: str | None = None
    huf_osszeg: float | None = None
    fizetve: bool | None = None
    megjegyzes: str | None = None


@router.put("/idoszakok/{idoszak_id}", response_model=IdoszakRead)
def update_idoszak(
    idoszak_id: int,
    payload: IdoszakIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Egy forduló tényleges adatai. Csak az elküldött mezőket írjuk át, hogy
    az összeg beírása ne törölje a megjegyzést (és fordítva)."""
    idoszak = db.get(KotelezettsegIdoszak, idoszak_id)
    if idoszak is None:
        raise HTTPException(status_code=404, detail="Az időszak nem található.")
    for mezo, ertek in payload.model_dump(exclude_unset=True).items():
        setattr(idoszak, mezo, ertek)
    db.commit()
    db.refresh(idoszak)
    darab = _szamlak(db, [idoszak.id])
    return IdoszakRead(
        id=idoszak.id,
        kotelezettseg_id=idoszak.kotelezettseg_id,
        esedekesseg=idoszak.esedekesseg,
        osszeg=float(idoszak.osszeg) if idoszak.osszeg is not None else None,
        plusz_afa=bool(idoszak.plusz_afa),
        brutto=brutto(float(idoszak.osszeg) if idoszak.osszeg is not None else None, bool(idoszak.plusz_afa)),
        penznem=idoszak.penznem,
        huf_osszeg=float(idoszak.huf_osszeg) if idoszak.huf_osszeg is not None else None,
        fizetve=idoszak.fizetve,
        megjegyzes=idoszak.megjegyzes,
        szamla_db=len(darab.get(idoszak.id, [])),
        szamlak=[DocumentAttachmentRead.model_validate(f) for f in darab.get(idoszak.id, [])],
        hianyzik=szolg.hianyzo_teendo(idoszak, bool(darab.get(idoszak.id))),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Google-táblázat import
# ─────────────────────────────────────────────────────────────────────────────


class ImportIn(BaseModel):
    #: A megosztott táblázat linkje - azt lehet a böngészőből kimásolni.
    url: str


class ImportEredmeny(BaseModel):
    beolvasott: int
    letrehozott: int
    frissitett: int
    #: Amelyik sornál nem sikerült a felelőst névre megtalálni - a sor bekerül,
    #: csak felelős nélkül, és itt jelezzük, kit kell kézzel beállítani.
    ismeretlen_felelosok: list[str] = []
    uzenet: str


@router.post("/import-google-tablazat", response_model=ImportEredmeny)
def import_google_tablazat(
    payload: ImportIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """A Google-táblázatban vezetett előfizetés-lista átemelése - TÜKÖRKÉNT.

    A felhasználó döntése (2026-08-30): az E-Rezsi pontosan azt mutassa, ami
    a táblázatban van - ezért az import egy-az-egyben tükör:
    - az azonosítás a (név, csomag) páros (azonos kulcsú sorok sorrendben
      párosulnak, hogy a többfiókos Adobe-sorok ne olvadjanak össze);
    - a FORDULÓT nem vesszük át, sőt töröljük: az E-Rezsi csak egy adatbázis
      arról, mennyit költünk és mikor - forduló-követés és jelzés nélkül
      (lásd services/kotelezettseg.py azonos szűrései);
    - ami előfizetés a táblázatban már nincs benne, azt innen is töröljük
      (a nem-előfizetés típusú sorokhoz - biztosítás, forgalmi - nem nyúlunk)."""
    try:
        csv_szoveg = kotelezettseg_import.letolt(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # hálózati hiba, 404, jogosultság
        raise HTTPException(status_code=502, detail=f"A táblázat nem érhető el: {exc}") from exc

    sorok = kotelezettseg_import.parse_sorok(csv_szoveg)
    emberek = {e.full_name.strip().lower(): e for e in db.scalars(select(Employee)).all()}

    # A meglévő ELŐFIZETÉS-sorok kulcsonként CSOPORTOSÍTVA, nem egyetlen
    # elemként: a táblázatban ugyanaz a szolgáltatás többször is szerepel
    # azonos névvel és csomaggal (három Adobe-előfizetés, más-más fiókból). A
    # fájl n-edik ilyen sora az n-edik meglévő sorra kerül - a futás stabil
    # és ismételhető. Csak az előfizetéseket nézzük: egy azonos nevű
    # biztosítást a tükör nem téríthet el.
    meglevok: dict[tuple, list[Kotelezettseg]] = {}
    for meglevo in db.scalars(
        select(Kotelezettseg).where(Kotelezettseg.tipus == KotelezettsegTipus.ELOFIZETES.value)
    ).all():
        kulcs = (meglevo.nev.strip().lower(), (meglevo.csomag or "").strip().lower())
        meglevok.setdefault(kulcs, []).append(meglevo)
    felhasznalt: dict[tuple, int] = {}
    erintett_idk: set[int] = set()

    letrehozott = frissitett = 0
    ismeretlen: list[str] = []
    for sor in sorok:
        felelos = emberek.get((sor.felelos_nev or "").strip().lower()) if sor.felelos_nev else None
        if sor.felelos_nev and felelos is None and sor.felelos_nev not in ismeretlen:
            ismeretlen.append(sor.felelos_nev)

        kulcs = (sor.nev.strip().lower(), (sor.csomag or "").strip().lower())
        sorszam = felhasznalt.get(kulcs, 0)
        felhasznalt[kulcs] = sorszam + 1
        csoport = meglevok.setdefault(kulcs, [])
        if sorszam < len(csoport):
            k = csoport[sorszam]
            frissitett += 1
        else:
            k = Kotelezettseg(nev=sor.nev, tipus=KotelezettsegTipus.ELOFIZETES.value)
            db.add(k)
            csoport.append(k)
            letrehozott += 1

        k.csomag = sor.csomag
        k.ciklus = sor.ciklus
        # FORDULÓ NINCS: az E-Rezsi csak egy adatbázis arról, mennyit költünk
        # és mikor - a megújulás-követést a felhasználó kivetette (a korábban
        # importált dátumokat is töröljük, ne maradjon "mikor újul" jelzés).
        k.fordulo_nap = None
        k.fordulo_honap = None
        k.kovetkezo_fordulo = None
        k.osztaly = sor.osztaly
        k.felelos_id = felelos.id if felelos else None
        k.aktiv = sor.aktiv
        k.ar_osszeg = sor.ar_osszeg
        k.ar_penznem = sor.ar_penznem
        k.huf_becsles_honap = sor.huf_becsles_honap
        k.huf_becsles_ev = sor.huf_becsles_ev
        k.szamla_forras = sor.szamla_forras
        k.kartya = sor.kartya
        k.megjegyzes = sor.megjegyzes
        db.flush()
        erintett_idk.add(k.id)

    # TÜKÖR-TAKARÍTÁS: az az előfizetés, ami a táblázatban már nincs benne,
    # innen is törlődik (az időszakaival együtt - cascade), hogy a lista
    # pontosan a táblázatot mutassa.
    torolt = 0
    for csoport in meglevok.values():
        for k in csoport:
            if k.id not in erintett_idk:
                db.delete(k)
                torolt += 1

    db.commit()
    szolg.ensure_mindent(db)
    return ImportEredmeny(
        beolvasott=len(sorok),
        letrehozott=letrehozott,
        frissitett=frissitett,
        ismeretlen_felelosok=ismeretlen,
        uzenet=(
            f"{len(sorok)} sor beolvasva: {letrehozott} új, {frissitett} frissítve"
            + (f", {torolt} törölve (a táblázatban már nincs benne)" if torolt else "")
            + "."
            + (f" Ismeretlen felelős: {', '.join(ismeretlen)}." if ismeretlen else "")
        ),
    )
