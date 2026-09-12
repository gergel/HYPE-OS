"""UTALÁSOK FELVEZETÉSE - HTTP-felület.

Egy már elutalt számlacsomag (ZIP) adminisztrálása: feltöltés + kötelező közös
utalási dátum → háttér-felismerés és párosítás → ellenőrző táblázat → a
KIJELÖLT tételek kifizetésének rögzítése → naplózott visszavonás. Banki
utalást nem indít. A jogosultság a Pénzügyek oldalé; a rögzítés "create"
(éles pénzügyi rekordot ír), a visszavonás "delete" jogot kér."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.employee import Employee, SystemRole
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.performance_certificate import PerformanceCertificate
from app.models.project_code import ProjectCode
from app.models.utalas_felvezetes import ELSZAMOLASOK, TETEL_ALLAPOTOK, UtalasAdag, UtalasTetel
from app.services import hatter_feladat, utalas_felvezetes
from app.services.utalas_felvezetes import UtalasHiba

router = APIRouter(prefix="/utalasok", tags=["utalasok"])

PAGE = "/penzugyek"
_MINDEN_SZEREPKOR = tuple(SystemRole)

MAX_ZIP_MERET = 400 * 1024 * 1024


# ── Kimeneti sémák ───────────────────────────────────────────────────────────


class TetelOut(BaseModel):
    id: int
    adag_id: int
    fajl_nev: str | None
    fajl_utvonal: str | None
    url: str | None
    content_type: str | None
    allapot: str
    allapot_cimke: str | None = None
    hiba_uzenet: str | None
    elszamolas: str
    szamlaszam: str | None
    kibocsato_nev: str | None
    kibocsato_adoszam: str | None
    vevo_nev: str | None
    dokumentum_tipus: str | None
    netto: float | None
    brutto: float | None
    penznem: str
    kiallitas_datuma: date | None
    teljesites_datuma: date | None
    fizetesi_hatarido: date | None
    cel_tipus: str | None
    cel_expense_id: int | None
    cel_certificate_id: int | None
    cel_internal_certificate_id: int | None
    uj_kiadas: dict | None
    javaslat: dict | None
    utalas_datum: date | None
    osszeg_elteres_elfogadva: bool
    duplikatum_tetel_id: int | None
    rogzitve_at: datetime | None
    rogzites_naplo: dict | None
    visszavonva_at: datetime | None
    # Kiegészítés a felületnek:
    cel_cimke: str | None = None
    cel_link: str | None = None
    cel_fizetesi_allapot: dict | None = None
    ervenyes_datum: date | None = None

    model_config = {"from_attributes": True}


class AdagOut(BaseModel):
    id: int
    nev: str | None
    megjegyzes: str | None
    utalas_datum: date
    zip_fajl_nev: str | None
    allapot: str
    hiba_uzenet: str | None
    fajl_darab: int
    kihagyott_fajlok: list | None
    created_at: datetime
    tetel_darab: int = 0
    rogzitett_darab: int = 0

    model_config = {"from_attributes": True}


class AdagReszlet(AdagOut):
    tetelek: list[TetelOut] = []


def _cel_reszletek(db: Session, t: UtalasTetel) -> tuple[str | None, str | None]:
    """(emberi címke, megnyitható link) a tétel céljához."""
    if t.cel_tipus == "kiadas" and t.cel_expense_id:
        exp = db.get(Expense, t.cel_expense_id)
        if exp is None:
            return ("A kiválasztott kiadás nem található", None)
        pc = db.get(ProjectCode, exp.project_code_id) if exp.project_code_id else None
        return (
            f"Kiadás #{exp.id}: {exp.megnevezes}" + (f" – {pc.projektkod}" if pc else ""),
            "/penzugyek/kiadas",
        )
    if t.cel_tipus == "kulsos_tig" and t.cel_certificate_id:
        cert = db.get(PerformanceCertificate, t.cel_certificate_id)
        if cert is None:
            return ("A kiválasztott TIG nem található", None)
        fel = cert.employee.full_name if cert.employee else (cert.vallalkozas.nev if cert.vallalkozas else "?")
        projekt = cert.project.nev if cert.project else None
        link = f"/projektek/{cert.project_id}" if cert.project_id else (
            f"/utokovetes/projektkodok/{cert.project_code_id}" if cert.project_code_id else "/utokovetes"
        )
        return (f"Külsős TIG – {fel}" + (f" – {projekt}" if projekt else ""), link)
    if t.cel_tipus == "belsos_tig" and t.cel_internal_certificate_id:
        cert = db.get(InternalPerformanceCertificate, t.cel_internal_certificate_id)
        if cert is None:
            return ("A kiválasztott belsős TIG nem található", None)
        nev = cert.employee.full_name if cert.employee else "?"
        return (
            f"Belsős TIG – {nev} – {cert.ev}.{cert.honap:02d}",
            f"/belsos-tig/{cert.employee_id}/{cert.ev}/{cert.honap}",
        )
    if t.cel_tipus == "uj_kiadas":
        adatok = t.uj_kiadas or {}
        pc = db.get(ProjectCode, adatok.get("project_code_id")) if adatok.get("project_code_id") else None
        return (
            "ÚJ kiadás készül" + (f" a(z) {pc.projektkod} kódra" if pc else (" (működési)" if adatok.get("mukodesi") else "")),
            None,
        )
    return (None, None)


def _tetel_out(db: Session, t: UtalasTetel) -> TetelOut:
    ki = TetelOut.model_validate(t)
    ki.allapot_cimke = TETEL_ALLAPOTOK.get(t.allapot, t.allapot)
    ki.cel_cimke, ki.cel_link = _cel_reszletek(db, t)
    ki.cel_fizetesi_allapot = utalas_felvezetes._cel_fizetesi_allapot(db, t)
    ki.ervenyes_datum = t.utalas_datum or t.adag.utalas_datum
    return ki


def _adag_out(db: Session, adag: UtalasAdag, reszletes: bool = False) -> AdagOut | AdagReszlet:
    tipus = AdagReszlet if reszletes else AdagOut
    ki = tipus.model_validate(adag)
    ki.tetel_darab = len(adag.tetelek)
    ki.rogzitett_darab = sum(1 for t in adag.tetelek if t.allapot == "rogzitve")
    if reszletes:
        ki.tetelek = [_tetel_out(db, t) for t in adag.tetelek]
    return ki


def _adag_lekeres(db: Session, adag_id: int) -> UtalasAdag:
    adag = db.scalar(
        select(UtalasAdag).options(selectinload(UtalasAdag.tetelek)).where(UtalasAdag.id == adag_id)
    )
    if adag is None:
        raise HTTPException(status_code=404, detail="Ez az adag nem található.")
    return adag


def _tetel_lekeres(db: Session, tetel_id: int, zarolva: bool = False) -> UtalasTetel:
    q = select(UtalasTetel).where(UtalasTetel.id == tetel_id)
    if zarolva:
        q = q.with_for_update()
    t = db.execute(q).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Ez a tétel nem található.")
    return t


# ── Adag létrehozása + listázás ──────────────────────────────────────────────


@router.post("", response_model=AdagOut)
async def adag_letrehozas(
    fajl: UploadFile = File(...),
    utalas_datum: str = Form(...),
    nev: str | None = Form(None),
    megjegyzes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """Új adag: ZIP + KÖTELEZŐ utalási dátum. A dátum a TÉNYLEGES banki utalás
    napja - nincs "észrevétlen mai nap" alapérték. A felismerés háttérben fut,
    az adag tartósan mentett (bezárás után folytatható)."""
    try:
        datum = date.fromisoformat(utalas_datum.strip())
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Add meg az utalás dátumát (ÉÉÉÉ-HH-NN).") from exc
    adat = await fajl.read()
    if not adat:
        raise HTTPException(status_code=400, detail="A feltöltött fájl üres.")
    if len(adat) > MAX_ZIP_MERET:
        raise HTTPException(status_code=400, detail="A ZIP túl nagy (a határ 400 MB).")
    try:
        adag, hatteradat = utalas_felvezetes.adag_letrehozas(
            db,
            zip_adat=adat,
            zip_nev=fajl.filename,
            utalas_datum=datum,
            nev=nev,
            megjegyzes=megjegyzes,
            letrehozo=current_user,
        )
    except UtalasHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hatter_feladat.inditas(
        f"utalas-adag-{adag.id}",
        lambda naplo: utalas_felvezetes.adag_feldolgozas(adag.id, hatteradat, naplo),
    )
    return _adag_out(db, adag)


@router.get("", response_model=list[AdagOut])
def adag_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    adagok = db.scalars(
        select(UtalasAdag).options(selectinload(UtalasAdag.tetelek)).order_by(UtalasAdag.id.desc()).limit(100)
    ).all()
    return [_adag_out(db, a) for a in adagok]


@router.get("/{adag_id}", response_model=AdagReszlet)
def adag_reszlet(
    adag_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    adag = _adag_lekeres(db, adag_id)
    # Beragadt háttér-feldolgozás felismerése (deploy/újraindítás közben):
    # ha a job nem fut, de az adag "feldolgozas"-ban maradt, újraindítjuk.
    if adag.allapot == "feldolgozas":
        feladat = hatter_feladat.allapot(db, f"utalas-adag-{adag.id}")
        if feladat is None or not feladat.running:
            maradek = [t for t in adag.tetelek if t.allapot == "feldolgozas"]
            if maradek:
                hatter_feladat.inditas(
                    f"utalas-adag-{adag.id}",
                    lambda naplo: utalas_felvezetes.adag_feldolgozas(adag.id, [], naplo),
                )
            else:
                adag.allapot = "ellenorzes"
                db.commit()
    return _adag_out(db, adag, reszletes=True)


@router.delete("/{adag_id}", response_model=None)
def adag_torles(
    adag_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Adag törlése - csak ha nincs benne felvezetett (nem visszavont) tétel."""
    adag = _adag_lekeres(db, adag_id)
    if any(t.allapot == "rogzitve" for t in adag.tetelek):
        raise HTTPException(
            status_code=400,
            detail="Az adagban felvezetett tétel van - előbb vond vissza a felvezetéseket, vagy hagyd meg az adagot naplónak.",
        )
    kulcsok = [t.storage_key for t in adag.tetelek if t.storage_key]
    db.delete(adag)
    db.commit()
    if kulcsok:
        import threading

        from app.services import document_storage

        def _takaritas(lista: list[str]) -> None:
            for k in lista:
                try:
                    document_storage.delete_object(k)
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_takaritas, args=(kulcsok,), daemon=True).start()
    return None


# ── Tétel-módosítás (ellenőrzés közben) ─────────────────────────────────────


class TetelPatch(BaseModel):
    elszamolas: str | None = None
    #: Tételi eltérő utalási dátum; "" (üres) = vissza az adag dátumára.
    utalas_datum: str | None = None
    cel_tipus: str | None = None
    cel_expense_id: int | None = None
    cel_certificate_id: int | None = None
    cel_internal_certificate_id: int | None = None
    uj_kiadas: dict | None = None
    osszeg_elteres_elfogadva: bool | None = None


@router.patch("/tetel/{tetel_id}", response_model=TetelOut)
def tetel_modositas(
    tetel_id: int,
    payload: TetelPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    t = _tetel_lekeres(db, tetel_id, zarolva=True)
    if t.allapot == "rogzitve":
        raise HTTPException(status_code=409, detail="Felvezetett tétel nem módosítható - előbb vond vissza.")
    if payload.elszamolas is not None:
        if payload.elszamolas not in ELSZAMOLASOK:
            raise HTTPException(status_code=400, detail=f"Ismeretlen elszámolás: {payload.elszamolas}")
        t.elszamolas = payload.elszamolas
    if payload.utalas_datum is not None:
        if payload.utalas_datum.strip() == "":
            t.utalas_datum = None
        else:
            try:
                t.utalas_datum = date.fromisoformat(payload.utalas_datum.strip())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Hibás dátum (ÉÉÉÉ-HH-NN).") from exc
    mezok = payload.model_dump(exclude_unset=True)
    if "cel_tipus" in mezok:
        if payload.cel_tipus is not None and payload.cel_tipus not in ("kiadas", "kulsos_tig", "belsos_tig", "uj_kiadas"):
            raise HTTPException(status_code=400, detail=f"Ismeretlen cél-típus: {payload.cel_tipus}")
        t.cel_tipus = payload.cel_tipus
        # Cél-váltásnál a másik típus azonosítói nem maradhatnak bent.
        if payload.cel_tipus != "kiadas":
            t.cel_expense_id = None
        if payload.cel_tipus != "kulsos_tig":
            t.cel_certificate_id = None
        if payload.cel_tipus != "belsos_tig":
            t.cel_internal_certificate_id = None
        t.osszeg_elteres_elfogadva = False
    if "cel_expense_id" in mezok and payload.cel_expense_id is not None:
        t.cel_tipus = "kiadas"
        t.cel_expense_id = payload.cel_expense_id
        t.cel_certificate_id = None
        t.cel_internal_certificate_id = None
    if "cel_certificate_id" in mezok and payload.cel_certificate_id is not None:
        t.cel_tipus = "kulsos_tig"
        t.cel_certificate_id = payload.cel_certificate_id
        t.cel_expense_id = None
        t.cel_internal_certificate_id = None
    if "cel_internal_certificate_id" in mezok and payload.cel_internal_certificate_id is not None:
        t.cel_tipus = "belsos_tig"
        t.cel_internal_certificate_id = payload.cel_internal_certificate_id
        t.cel_expense_id = None
        t.cel_certificate_id = None
    if payload.uj_kiadas is not None:
        t.cel_tipus = "uj_kiadas"
        t.uj_kiadas = {**(t.uj_kiadas or {}), **payload.uj_kiadas}
    if payload.osszeg_elteres_elfogadva is not None:
        t.osszeg_elteres_elfogadva = payload.osszeg_elteres_elfogadva
    # A TIG-ből származó kiadássor itt is átirányul az eredeti TIG-re.
    utalas_felvezetes._tig_kiadas_atiranyitas(db, t)
    t.hiba_uzenet = None
    if t.allapot != "feldolgozas":
        utalas_felvezetes.allapot_ujraertekeles(db, t)
    db.commit()
    db.refresh(t)
    return _tetel_out(db, t)


@router.post("/tetel/{tetel_id}/ujrafeldolgozas", response_model=TetelOut)
def tetel_ujrafeldolgozas(
    tetel_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    t = _tetel_lekeres(db, tetel_id, zarolva=True)
    if t.allapot == "rogzitve":
        raise HTTPException(status_code=409, detail="Felvezetett tétel nem dolgozható fel újra.")
    t.hiba_uzenet = None
    t.duplikatum_tetel_id = None
    utalas_felvezetes.tetel_feldolgozas(db, t)
    db.commit()
    db.refresh(t)
    return _tetel_out(db, t)


# ── Tömeges elszámolás-állítás ───────────────────────────────────────────────


class ElszamolasIn(BaseModel):
    tetel_idk: list[int]
    elszamolas: str


@router.post("/{adag_id}/elszamolas")
def tomeges_elszamolas(
    adag_id: int,
    payload: ElszamolasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Kijelölt sorokra alkalmazható tömeges HYPE/Krumpello választás."""
    if payload.elszamolas not in ELSZAMOLASOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen elszámolás: {payload.elszamolas}")
    adag = _adag_lekeres(db, adag_id)
    modositott = 0
    for t in adag.tetelek:
        if t.id in set(payload.tetel_idk) and t.allapot != "rogzitve":
            t.elszamolas = payload.elszamolas
            modositott += 1
    db.commit()
    return {"modositott": modositott}


# ── Kifizetés rögzítése (kijelöltek) ─────────────────────────────────────────


class RogzitesIn(BaseModel):
    tetel_idk: list[int]


@router.post("/{adag_id}/rogzites")
def kijeloltek_rogzitese(
    adag_id: int,
    payload: RogzitesIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """A kijelölt tételek kifizetésének VÉGLEGES felvezetése - tételenként
    külön tranzakcióban: részleges hiba esetén pontosan látszik, mi sikerült,
    és az újrapróbálás csak a maradékot végzi el. A problémás sorok az
    adagban maradnak, nem akadályozzák az egyértelműeket."""
    _adag_lekeres(db, adag_id)
    eredmenyek: list[dict] = []
    for tid in payload.tetel_idk:
        try:
            t = db.execute(
                select(UtalasTetel).where(UtalasTetel.id == tid, UtalasTetel.adag_id == adag_id).with_for_update()
            ).scalar_one_or_none()
            if t is None:
                eredmenyek.append({"tetel_id": tid, "siker": False, "hiba": "A tétel nem található."})
                continue
            naplo = utalas_felvezetes.tetel_rogzites(db, t, current_user)
            db.commit()
            eredmenyek.append({"tetel_id": tid, "siker": True, "mar_rogzitve": bool(naplo.get("mar_rogzitve"))})
        except UtalasHiba as exc:
            # Az állapot-átsorolást (pl. mar_kifizetve / osszeg_elter) és a
            # hibaüzenetet MEGTARTJUK - csak a félbemaradt pénzügyi írások
            # gördülnek vissza (a tetel_rogzites az állapotot a kivétel ELŐTT
            # állítja, ezért azt újra beírjuk a rollback után).
            uj_allapot = None
            t2 = db.get(UtalasTetel, tid)
            if t2 is not None:
                uj_allapot = t2.allapot
            db.rollback()
            t2 = db.get(UtalasTetel, tid)
            if t2 is not None:
                if uj_allapot and uj_allapot != "rogzitve":
                    t2.allapot = uj_allapot
                t2.hiba_uzenet = str(exc)
                db.commit()
            eredmenyek.append({"tetel_id": tid, "siker": False, "hiba": str(exc)})
        except Exception as exc:  # noqa: BLE001 - egy tétel hibája ne állítsa meg a többit
            db.rollback()
            import logging

            logging.getLogger(__name__).exception("Utalás-rögzítési hiba (tétel #%s)", tid)
            eredmenyek.append({"tetel_id": tid, "siker": False, "hiba": f"{type(exc).__name__}: {exc}"})
    return {
        "sikeres": sum(1 for e in eredmenyek if e["siker"]),
        "sikertelen": sum(1 for e in eredmenyek if not e["siker"]),
        "eredmenyek": eredmenyek,
    }


# ── Visszavonás ──────────────────────────────────────────────────────────────


class VisszavonasIn(BaseModel):
    tetel_idk: list[int]


@router.post("/{adag_id}/visszavonas")
def felvezetes_visszavonasa(
    adag_id: int,
    payload: VisszavonasIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """A felvezetés ADMINISZTRÁCIÓJÁNAK visszavonása (a banki utalást nem
    érinti): csak az adott felvezetés naplózott változásait állítja vissza,
    a későbbi kézi módosításokat nem írja felül."""
    _adag_lekeres(db, adag_id)
    eredmenyek: list[dict] = []
    for tid in payload.tetel_idk:
        try:
            t = db.execute(
                select(UtalasTetel).where(UtalasTetel.id == tid, UtalasTetel.adag_id == adag_id).with_for_update()
            ).scalar_one_or_none()
            if t is None:
                eredmenyek.append({"tetel_id": tid, "siker": False, "hiba": "A tétel nem található."})
                continue
            eredmeny = utalas_felvezetes.tetel_visszavonas(db, t, current_user)
            db.commit()
            eredmenyek.append({"tetel_id": tid, "siker": True, "eredmeny": eredmeny})
        except UtalasHiba as exc:
            db.rollback()
            eredmenyek.append({"tetel_id": tid, "siker": False, "hiba": str(exc)})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            import logging

            logging.getLogger(__name__).exception("Utalás-visszavonási hiba (tétel #%s)", tid)
            eredmenyek.append({"tetel_id": tid, "siker": False, "hiba": f"{type(exc).__name__}: {exc}"})
    return {
        "sikeres": sum(1 for e in eredmenyek if e["siker"]),
        "sikertelen": sum(1 for e in eredmenyek if not e["siker"]),
        "eredmenyek": eredmenyek,
    }
