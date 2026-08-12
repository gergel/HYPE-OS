"""Szerződésmódosítások - KÖZÖS végpontkészlet minden keretszerződéshez.

Ugyanaz a folyamat kell a MEGRENDELŐI keretszerződéshez (ügyfél felé) és a
CÉGES keretszerződéshez (számlázó cég felé): generálás a sablonból vagy saját
papír feltöltése, kiküldés után "Aláírásra vár", és az aláírva visszakapott
példánytól "Kész".

Mivel mindkettő ugyanaz az entitás (`Contract`), a módosítás pedig már eleve
`contract_id`-re mutat (lásd models/keret_modositas.py), a két oldal
KÜLÖNBSÉGE csak annyi, hogy melyik szerződést engedik el a saját `_get_or_404`
függvényükben, és melyik oldal jogosultságát kérik. Ezért nem másoltuk a
végpontokat: ez a modul egy gyár, amit mindkét router felfűz magára.

Két másolatból előbb-utóbb két, egymástól elcsúszó viselkedés lenne - és épp
ezen a folyamaton drága a csúszás: egy papír, amit az egyik oldalon lezártnak
mutat a rendszer, a másikon meg nem."""

from __future__ import annotations

import os
from datetime import date
from typing import Callable

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.keret_modositas import ALLAPOTOK, KeretModositas
from app.services import document_storage, keret_modositas


class KeretModositasRead(BaseModel):
    """Egy szerződésmódosítás a keretszerződéshez.

    Az `allapot` útja: Készítés alatt -> Aláírásra vár -> Kész. A többi papírtól
    eltérően itt a KIKÜLDÉS még nem a végállomás: a módosítás akkor ér valamit,
    ha aláírva visszajött (lásd models/keret_modositas.py)."""

    id: int
    contract_id: int
    keltezes: date | None = None
    allapot: str | None = None
    file_url: str | None = None
    alairt_file_url: str | None = None
    email: str | None = None
    #: Mire és mikor szólt az EREDETI szerződés - a módosítás szövege ezekre
    #: hivatkozik vissza.
    megbizas_targya: str | None = None
    szerzodes_letrejotte: date | None = None
    kikuldve: date | None = None
    kikuldte: str | None = None
    #: A kiküldött kísérőlevél szövege, ahogy megírták (aláírás nélkül).
    level_szoveg: str | None = None
    megjegyzes: str | None = None


class ModositasKuldesIn(BaseModel):
    """A kiküldés bemenete: a kísérőlevél és a dokumentum kitöltendő mezői.

    Mindegyik elhagyható, és a végpont törzs nélkül is hívható - ilyenkor a
    levél alapszövege megy, a három dokumentum-mezőt pedig a keret adja (lásd
    services/keret_modositas.uj_modositas). A felületen viszont mindig kitöltve
    érkeznek, mert ott a küldő előtt van, mi kerül a papírra."""

    level_szoveg: str | None = None
    keltezes: date | None = None
    megbizas_targya: str | None = None
    szerzodes_letrejotte: date | None = None


class ModositasIn(BaseModel):
    keltezes: date | None = None
    megbizas_targya: str | None = None
    szerzodes_letrejotte: date | None = None
    allapot: str | None = None
    megjegyzes: str | None = None


def modositas_kimenet(m: KeretModositas) -> KeretModositasRead:
    return KeretModositasRead(
        id=m.id,
        contract_id=m.contract_id,
        keltezes=m.keltezes,
        allapot=m.allapot,
        file_url=m.file_url,
        alairt_file_url=m.alairt_file_url,
        email=m.email,
        megbizas_targya=m.megbizas_targya,
        szerzodes_letrejotte=m.szerzodes_letrejotte,
        kikuldve=m.kikuldve.date() if m.kikuldve else None,
        kikuldte=m.kikuldte.full_name if m.kikuldte else None,
        level_szoveg=m.level_szoveg,
        megjegyzes=m.megjegyzes,
    )


def modositas_or_404(db: Session, keret_id: int, modositas_id: int) -> KeretModositas:
    m = db.get(KeretModositas, modositas_id)
    if m is None or m.contract_id != keret_id:
        raise HTTPException(status_code=404, detail="Ez a szerződésmódosítás nem található.")
    return m


async def modositas_fajl(db: Session, m: KeretModositas, file: UploadFile, *, alairt: bool) -> None:
    """Feltöltés a módosításhoz - saját vagy aláírt példány.

    Az ALÁÍRT példány zárja le a folyamatot: ettől lesz "Kész". A saját fájl
    csak a papírt pótolja (van, amit nem itt generáltak), tehát az továbbra is
    aláírásra vár."""
    data = await file.read()
    kiterjesztes = os.path.splitext(file.filename or "")[1] or ".pdf"
    kulcs = f"keret-modositas{'-alairt' if alairt else ''}/{m.id}{kiterjesztes}"
    regi = m.alairt_file_storage_key if alairt else m.file_storage_key
    url = document_storage.upload_bytes(data, kulcs, file.content_type or "application/octet-stream")
    if alairt:
        m.alairt_file_url, m.alairt_file_storage_key = url, kulcs
        m.allapot = "Kész"
    else:
        m.file_url, m.file_storage_key = url, kulcs
        if m.allapot == "Készítés alatt":
            m.allapot = "Aláírásra vár"
    db.commit()
    if regi and regi != kulcs:
        document_storage.delete_object(regi)


def epits_modositas_utvonalakat(
    router: APIRouter,
    *,
    page: str,
    keret_betoltes: Callable[[Session, int], Contract],
    generalas: bool = True,
) -> None:
    """A `/{keret_id}/modositasok...` végpontok felfűzése egy meglévő routerre.

    `keret_betoltes`: a hívó oldal saját ellenőrzése (megvan-e, és a MEGFELELŐ
    fajta keretszerződés-e). Ezért paraméter: a megrendelői oldal mást enged
    el, mint a céges.

    `generalas`: kerüljön-e fel a sablonból generáló+kiküldő végpont. A CÉGES
    keretszerződésnél NEM: a sablon a MEGRENDELŐI viszonyra van írva (ott mi
    vagyunk a megbízott), egy alvállalkozói keret módosításán viszont a
    szerepek fordítottak - abból a sablonból ott hibás papír lenne. Ezen az
    oldalon a kész módosító dokumentum feltölthető, és onnantól ugyanúgy
    aláírásra vár."""

    @router.get("/{keret_id}/modositasok", response_model=list[KeretModositasRead])
    def list_modositasok(
        keret_id: int,
        db: Session = Depends(get_db),
        _user: Employee = Depends(get_current_user),
    ):
        c = keret_betoltes(db, keret_id)
        return [modositas_kimenet(m) for m in c.modositasok]

    @router.post(
        "/{keret_id}/modositasok/generalas-es-kuldes",
        response_model=KeretModositasRead,
        status_code=201,
        include_in_schema=generalas,
    )
    def modositas_generalas_es_kuldes(
        keret_id: int,
        payload: ModositasKuldesIn | None = None,
        db: Session = Depends(get_db),
        user: Employee = Depends(require_page_action(page, "create")),
    ):
        """Szerződésmódosítás generálása a sablonból és kiküldése.

        A levél az admin fiókból megy, a felhasználó által megírt szöveggel és
        a fiók Gmailben beállított aláírásával; a kész PDF a Drive mappába
        kerül - a részletek és az OK a services/keret_modositas.py-ban."""
        if not generalas:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Ehhez a keretszerződéshez nincs módosítás-sablon: a meglévő a megrendelői "
                    "viszonyra szól, ahol a szerepek fordítottak. Töltsd fel a kész módosító "
                    "dokumentumot - onnantól ugyanúgy aláírásra vár."
                ),
            )
        c = keret_betoltes(db, keret_id)
        try:
            m = keret_modositas.generalj_es_kuldj(
                db,
                c,
                user,
                level_szoveg=payload.level_szoveg if payload else None,
                keltezes=payload.keltezes if payload else None,
                megbizas_targya=payload.megbizas_targya if payload else None,
                szerzodes_letrejotte=payload.szerzodes_letrejotte if payload else None,
            )
        except RuntimeError as exc:
            # A félbemaradt sor MARADJON meg "Készítés alatt" állapotban: abból
            # látszik, hogy elindult egy kiküldés és hol akadt el.
            db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        db.commit()
        db.refresh(m)
        return modositas_kimenet(m)

    @router.post("/{keret_id}/modositasok/sajat-fajl", response_model=KeretModositasRead, status_code=201)
    async def modositas_sajat_fajl(
        keret_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        _user: Employee = Depends(require_page_action(page, "create")),
    ):
        """SAJÁT módosítás feltöltése a generálás helyett - van, amit a másik
        fél ad a saját sablonjával, és van, ami még a rendszer előtti."""
        c = keret_betoltes(db, keret_id)
        m = keret_modositas.uj_modositas(c)
        db.add(m)
        db.flush()
        await modositas_fajl(db, m, file, alairt=False)
        db.refresh(m)
        return modositas_kimenet(m)

    @router.post("/{keret_id}/modositasok/{modositas_id}/alairt-fajl", response_model=KeretModositasRead)
    async def modositas_alairt_fajl(
        keret_id: int,
        modositas_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        _user: Employee = Depends(require_page_action(page, "edit")),
    ):
        """Az aláírva visszakapott módosítás feltöltése - ettől lesz kész."""
        keret_betoltes(db, keret_id)
        m = modositas_or_404(db, keret_id, modositas_id)
        await modositas_fajl(db, m, file, alairt=True)
        db.refresh(m)
        return modositas_kimenet(m)

    @router.patch("/{keret_id}/modositasok/{modositas_id}", response_model=KeretModositasRead)
    def modositas_update(
        keret_id: int,
        modositas_id: int,
        payload: ModositasIn,
        db: Session = Depends(get_db),
        _user: Employee = Depends(require_page_action(page, "edit")),
    ):
        keret_betoltes(db, keret_id)
        m = modositas_or_404(db, keret_id, modositas_id)
        adat = payload.model_dump(exclude_unset=True)
        if "allapot" in adat and adat["allapot"] not in ALLAPOTOK:
            raise HTTPException(
                status_code=400,
                detail=f"Ismeretlen állapot. Használható: {', '.join(ALLAPOTOK)}.",
            )
        for mezo, ertek in adat.items():
            setattr(m, mezo, ertek)
        db.commit()
        db.refresh(m)
        return modositas_kimenet(m)

    @router.delete("/{keret_id}/modositasok/{modositas_id}", status_code=204)
    def modositas_delete(
        keret_id: int,
        modositas_id: int,
        db: Session = Depends(get_db),
        _user: Employee = Depends(require_page_action(page, "delete")),
    ):
        keret_betoltes(db, keret_id)
        m = modositas_or_404(db, keret_id, modositas_id)
        kulcsok = [k for k in (m.file_storage_key, m.alairt_file_storage_key) if k]
        db.delete(m)
        db.commit()
        for k in kulcsok:
            document_storage.delete_object(k)
