"""Vágói játék - havi pontverseny a vágók között.

A pontozás a MEGLÉVŐ munkából jön, nem külön adminisztrációból: az
ellenőrzésbe tett anyag és a lemért vágási idő úgyis keletkezik. Ez fontos,
mert egy játék, amiért külön adatot kell vezetni, két hét után elhal.

Külön jogosultsági oldal ("/vagoi-jatek"): az állás mindenkinek látszik, akit
beengedünk (a verseny lényege, hogy lássák egymást), de a nyeremény
kihirdetése és a munkanapok állítása szerkesztési jog.
"""

from __future__ import annotations

from datetime import date

import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee
from app.models.vagoi_jatek import (
    ALAP_MUNKANAP,
    ELLENORZES_PONT,
    PERC_PER_PONT,
    VagoJatekHonap,
    VagoJatekNap,
)
from app.services import document_storage, vagoi_jatek

router = APIRouter(prefix="/vagoi-jatek", tags=["vagoi-jatek"])

PAGE = "/vagoi-jatek"


class AllasOut(BaseModel):
    employee_id: int
    nev: str
    ellenorzes_db: int
    ellenorzes_pont: int
    vagas_perc: float
    vagas_pont: int
    nyers_pont: int
    munkanap: int
    pont: int
    helyezes: int


class HonapOut(BaseModel):
    ev: int
    honap: int
    #: Mi a nyeremény. Üres = még nincs kihirdetve.
    nyeremeny: str | None = None
    megjegyzes: str | None = None
    #: Fotó a nyereményről.
    kep_url: str | None = None
    #: Folyamatban van-e még (a mai hónap), vagy már lezárult.
    folyamatban: bool = False
    allas: list[AllasOut] = []
    #: A hónap győztese - lezárt hónapnál ő kapta a nyereményt.
    gyoztes_nev: str | None = None
    gyoztes_pont: int = 0


class SzabalyokOut(BaseModel):
    """A pontozás szabályai - a felület ebből írja ki a magyarázatot, hogy a
    számok ne a kódban ELREJTVE éljenek."""

    ellenorzes_pont: int = ELLENORZES_PONT
    perc_per_pont: int = PERC_PER_PONT
    alap_munkanap: int = ALAP_MUNKANAP


def _ma() -> tuple[int, int]:
    m = date.today()
    return m.year, m.month


def _allas_kimenet(allas: list[vagoi_jatek.Allas]) -> list[AllasOut]:
    return [
        AllasOut(
            employee_id=a.employee_id,
            nev=a.nev,
            ellenorzes_db=a.ellenorzes_db,
            ellenorzes_pont=a.ellenorzes_pont,
            vagas_perc=round(a.vagas_perc, 1),
            vagas_pont=a.vagas_pont,
            nyers_pont=a.nyers_pont,
            munkanap=a.munkanap,
            pont=a.pont,
            helyezes=a.helyezes,
        )
        for a in allas
    ]


def _honap_kimenet(db: Session, ev: int, honap: int) -> HonapOut:
    beallitas = vagoi_jatek.honap_beallitas(db, ev, honap)
    allas = vagoi_jatek.honap_allasa(db, ev, honap)
    folyo_ev, folyo_honap = _ma()
    gyoztes = next((a for a in allas if a.helyezes == 1), None)
    return HonapOut(
        ev=ev,
        honap=honap,
        nyeremeny=beallitas.nyeremeny if beallitas else None,
        megjegyzes=beallitas.megjegyzes if beallitas else None,
        kep_url=beallitas.kep_url if beallitas else None,
        folyamatban=(ev, honap) == (folyo_ev, folyo_honap),
        allas=_allas_kimenet(allas),
        gyoztes_nev=gyoztes.nev if gyoztes else None,
        gyoztes_pont=gyoztes.pont if gyoztes else 0,
    )


@router.get("/szabalyok", response_model=SzabalyokOut)
def get_szabalyok(_user: Employee = Depends(get_current_user)):
    return SzabalyokOut()


@router.get("/honap", response_model=HonapOut)
def get_honap(
    ev: int | None = None,
    honap: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy hónap versenye. Paraméter nélkül a FOLYÓ hónap - az érdekes."""
    folyo_ev, folyo_honap = _ma()
    return _honap_kimenet(db, ev or folyo_ev, honap or folyo_honap)


@router.get("/korabbi", response_model=list[HonapOut])
def get_korabbi(
    darab: int = 6,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """A korábbi hónapok eredménye, a legfrissebbel elöl.

    Csak azok a hónapok jönnek vissza, amikben TÖRTÉNT valami: egy üres hónap
    (nem volt még a rendszer, vagy nyaralás volt) nem eredmény, csak üres sor
    a dicsőségtáblán."""
    folyo_ev, folyo_honap = _ma()
    eredmeny: list[HonapOut] = []
    for ev, honap in vagoi_jatek.elozo_honapok(folyo_ev, folyo_honap, max(darab, 1)):
        adat = _honap_kimenet(db, ev, honap)
        if adat.allas:
            eredmeny.append(adat)
    return eredmeny


class NyeremenyIn(BaseModel):
    ev: int
    honap: int
    nyeremeny: str | None = None
    megjegyzes: str | None = None


@router.put("/nyeremeny", response_model=HonapOut)
def set_nyeremeny(
    payload: NyeremenyIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A hónap nyereményének kihirdetése (vagy javítása).

    Upsert: a hónapnak egy sora van, tehát az újbóli mentés felülír - nem
    keletkezhet két nyeremény ugyanarra a hónapra."""
    sor = vagoi_jatek.honap_beallitas(db, payload.ev, payload.honap)
    if sor is None:
        sor = VagoJatekHonap(ev=payload.ev, honap=payload.honap)
        db.add(sor)
    sor.nyeremeny = (payload.nyeremeny or "").strip() or None
    sor.megjegyzes = (payload.megjegyzes or "").strip() or None
    db.commit()
    return _honap_kimenet(db, payload.ev, payload.honap)


#: Amit képként elfogadunk. Szűk, zárt lista: ez a kép egy publikus URL-ről
#: jelenik meg a felületen, tehát nem lehet bármilyen fájlt "képként"
#: feltölteni és a tárhelyen keresztül kiszolgálni.
KEP_TIPUSOK = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/avif"}
#: Egy nyeremény-fotóhoz ennél nagyobb fájl nem kell (telefonos kép is elfér).
MAX_KEP_MERET = 10 * 1024 * 1024


def _honap_sor(db: Session, ev: int, honap: int) -> VagoJatekHonap:
    sor = vagoi_jatek.honap_beallitas(db, ev, honap)
    if sor is None:
        sor = VagoJatekHonap(ev=ev, honap=honap)
        db.add(sor)
        db.flush()
    return sor


@router.post("/nyeremeny-kep", response_model=HonapOut)
async def upload_nyeremeny_kep(
    ev: int,
    honap: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Fotó feltöltése a hónap nyereményéről.

    Egy hónapnak EGY képe van: az újabb feltöltés lecseréli az előzőt, és a
    régi objektumot el is dobjuk a tárhelyről - egy nyereményből nem lesz
    galéria, viszont a lecserélt kép sem marad ott örökre.

    A csere törlése CSAK a sikeres mentés után történik: ha a feltöltés
    elhasal, ne maradjunk se régi, se új képpel."""
    content_type = (file.content_type or "").lower()
    if content_type not in KEP_TIPUSOK:
        raise HTTPException(
            status_code=400,
            detail="Csak képet lehet feltölteni (JPG, PNG, WEBP, GIF, HEIC, AVIF).",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="A fájl üres.")
    if len(data) > MAX_KEP_MERET:
        raise HTTPException(
            status_code=400,
            detail=f"A kép túl nagy ({len(data) // 1024 // 1024} MB). A megengedett méret {MAX_KEP_MERET // 1024 // 1024} MB.",
        )

    sor = _honap_sor(db, ev, honap)
    regi_kulcs = sor.kep_storage_key
    kiterjesztes = os.path.splitext(file.filename or "")[1] or ".jpg"
    # A kulcs EGYEDI (uuid), nem csak a hónapból képzett - különben a csere
    # ugyanarra az URL-re írna, és a böngésző (meg a CDN) a gyorsítótárból
    # továbbra is a RÉGI képet mutatná. Új kulcs = új URL = azonnal látszik,
    # amit feltöltöttek; a régi objektumot pedig a mentés után eldobjuk.
    kulcs = f"vagoi-jatek-nyeremeny/{ev}-{honap:02d}-{uuid4().hex[:12]}{kiterjesztes}"
    try:
        sor.kep_url = document_storage.upload_bytes(data, kulcs, content_type)
    except RuntimeError as exc:
        # Nincs beállítva a tárhely - beszédes hiba a néma 500 helyett.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    sor.kep_storage_key = kulcs
    db.commit()

    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    return _honap_kimenet(db, ev, honap)


@router.delete("/nyeremeny-kep", response_model=HonapOut)
def delete_nyeremeny_kep(
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    sor = vagoi_jatek.honap_beallitas(db, ev, honap)
    if sor is None or not sor.kep_url:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nincs feltöltött kép.")
    kulcs = sor.kep_storage_key
    sor.kep_url = None
    sor.kep_storage_key = None
    db.commit()
    if kulcs:
        document_storage.delete_object(kulcs)
    return _honap_kimenet(db, ev, honap)


class MunkanapIn(BaseModel):
    ev: int
    honap: int
    employee_id: int
    munkanap: int


@router.put("/munkanap", response_model=HonapOut)
def set_munkanap(
    payload: MunkanapIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Hány munkanapja van valakinek abban a hónapban - ettől lesz igazságos a
    verseny (lásd models/vagoi_jatek.py VagoJatekNap).

    Menet közben is állítható: ha valaki megbetegszik vagy plusz napot vállal,
    az átírás után az állás azonnal újraszámolódik. A pontokat nem kell
    hozzányúlni - azok a nyers teljesítményt őrzik, az arányosítás pedig
    mindig a friss munkanapszámmal fut le."""
    if not 0 <= payload.munkanap <= 31:
        raise HTTPException(status_code=400, detail="A munkanapok száma 0 és 31 között lehet.")
    if db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=404, detail="Ez a munkatárs nem található.")
    sor = db.scalar(
        select(VagoJatekNap).where(
            VagoJatekNap.ev == payload.ev,
            VagoJatekNap.honap == payload.honap,
            VagoJatekNap.employee_id == payload.employee_id,
        )
    )
    if sor is None:
        sor = VagoJatekNap(ev=payload.ev, honap=payload.honap, employee_id=payload.employee_id)
        db.add(sor)
    sor.munkanap = payload.munkanap
    db.commit()
    return _honap_kimenet(db, payload.ev, payload.honap)
