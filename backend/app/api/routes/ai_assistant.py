"""AI Assistant - kérdés-válasz ÉS műveleti asszisztens (lásd
app/services/ai_assistant.py + ai_eszkozok.py).

A beszélgetések TARTÓSAK (ai_beszelgetesek): oldalfrissítés után a valós
állapot visszaáll, a folyamat-események és a művelet-napló az adatbázisban
él, nem a modell memóriájában. Minden beszélgetés a saját gazdájáé - más
felhasználó beszélgetését (és rajta keresztül az adatait) senki nem éri el.
A tényleges adathozzáférés és minden művelet a bejelentkezett felhasználó
saját jogosultságával fut."""

import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ai_beszelgetes import AiBeszelgetes, AiFajl, AiMuvelet, AiUzenet
from app.models.employee import Employee
from app.services import ai_assistant, ai_eszkozok, document_storage

router = APIRouter(prefix="/ai-assistant", tags=["ai-assistant"])

MAX_FAJL_MERET = 25 * 1024 * 1024


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    """A régi, beszélgetés nélküli kérdés-válasz végpont - megmarad a
    kompatibilitásért; az új felület a beszélgetéses végpontokat használja."""
    return AskResponse(answer=ai_assistant.ask(db, current_user, payload.question))


# ── Tartós beszélgetések ─────────────────────────────────────────────────────


def _sajat_beszelgetes(db: Session, user: Employee, beszelgetes_id: int) -> AiBeszelgetes:
    b = db.get(AiBeszelgetes, beszelgetes_id)
    if b is None or b.employee_id != user.id:
        # 404, nem 403: más beszélgetésének a léte sem információ.
        raise HTTPException(status_code=404, detail="Nincs ilyen beszélgetés.")
    return b


class BeszelgetesOut(BaseModel):
    id: int
    cim: str | None
    fut: bool
    updated_at: object = None

    model_config = {"from_attributes": True}


class UzenetOut(BaseModel):
    id: int
    szerep: str
    szoveg: str | None
    adat: dict | None
    created_at: object = None

    model_config = {"from_attributes": True}


@router.get("/beszelgetesek")
def beszelgetesek(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)):
    sorok = db.scalars(
        select(AiBeszelgetes)
        .where(AiBeszelgetes.employee_id == user.id)
        .order_by(AiBeszelgetes.updated_at.desc())
        .limit(50)
    ).all()
    return [BeszelgetesOut.model_validate(b) for b in sorok]


@router.post("/beszelgetesek", status_code=201)
def uj_beszelgetes(db: Session = Depends(get_db), user: Employee = Depends(get_current_user)):
    b = AiBeszelgetes(employee_id=user.id)
    db.add(b)
    db.commit()
    db.refresh(b)
    return BeszelgetesOut.model_validate(b)


@router.delete("/beszelgetesek/{beszelgetes_id}")
def beszelgetes_torles(
    beszelgetes_id: int, db: Session = Depends(get_db), user: Employee = Depends(get_current_user)
):
    """A beszélgetés törlése a csatolt fájljaival együtt. A művelet-napló
    hatásait (elvégzett módosítások) ez NEM vonja vissza - azok az érintett
    rekordokon élnek tovább, a saját visszavonási útjaikkal."""
    b = _sajat_beszelgetes(db, user, beszelgetes_id)
    for f in db.scalars(select(AiFajl).where(AiFajl.beszelgetes_id == b.id)):
        try:
            document_storage.delete_object(f.storage_key)
        except Exception:  # noqa: BLE001 - a tárhely-hiba ne akassza meg a törlést
            pass
    db.delete(b)
    db.commit()
    return {"ok": True}


@router.get("/beszelgetesek/{beszelgetes_id}/uzenetek")
def uzenetek(
    beszelgetes_id: int,
    utani: int = 0,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """A beszélgetés bejegyzései - `utani` (üzenet-id) fölöttiek: a felület
    futó kör közben ezzel pollozza az új folyamat-eseményeket."""
    b = _sajat_beszelgetes(db, user, beszelgetes_id)
    sorok = db.scalars(
        select(AiUzenet)
        .where(AiUzenet.beszelgetes_id == b.id, AiUzenet.id > utani)
        .order_by(AiUzenet.id)
    ).all()
    return {"fut": b.fut, "uzenetek": [UzenetOut.model_validate(u) for u in sorok]}


@router.post("/beszelgetesek/{beszelgetes_id}/fajl", status_code=201)
async def fajl_feltoltes(
    beszelgetes_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Fájl csatolása a beszélgetéshez - a tárhelyre kerül, az eszközök
    (számla-érkeztetés, dokumentum-csatolás) fajl_id-vel hivatkozzák."""
    b = _sajat_beszelgetes(db, user, beszelgetes_id)
    adat = await file.read()
    if not adat:
        raise HTTPException(status_code=400, detail="A fájl üres.")
    if len(adat) > MAX_FAJL_MERET:
        raise HTTPException(status_code=400, detail=f"A fájl túl nagy ({len(adat) // 1024 // 1024} MB) - a határ 25 MB.")
    f = AiFajl(
        beszelgetes_id=b.id,
        fajl_nev=(file.filename or "fajl")[:255],
        content_type=(file.content_type or "application/octet-stream").split(";")[0],
        meret_bajt=len(adat),
        storage_key="",
    )
    db.add(f)
    db.flush()
    kulcs = f"ai-chat/{b.id}/{f.id}-{re.sub(r'[^A-Za-z0-9._-]+', '_', f.fajl_nev)[:80]}"
    f.url = document_storage.upload_bytes(adat, kulcs, f.content_type or "application/octet-stream")
    f.storage_key = kulcs
    db.commit()
    return {"fajl_id": f.id, "nev": f.fajl_nev, "tipus": f.content_type, "meret_bajt": f.meret_bajt}


@router.post("/atiras")
async def atiras(
    file: UploadFile = File(...),
    _user: Employee = Depends(get_current_user),
):
    """DIKTÁLÁS-átírás: hangfelvétel → szöveg. Tartalék út azokra a
    böngészőkre, ahol nincs beépített beszédfelismerés - az eredmény a
    beviteli mezőbe kerül, a felhasználó javíthatja és ő küldi el (az átírás
    önmagában semmit nem hajt végre)."""
    adat = await file.read()
    if not adat:
        raise HTTPException(status_code=400, detail="Üres hangfelvétel.")
    if len(adat) > MAX_FAJL_MERET:
        raise HTTPException(status_code=400, detail="A felvétel túl hosszú (25 MB felett).")
    try:
        szoveg = ai_assistant.hang_atiras(adat, (file.content_type or "audio/webm").split(";")[0])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"szoveg": szoveg}


class UzenetIn(BaseModel):
    szoveg: str
    #: Az oldal, ahonnan a felhasználó az asszisztenst nyitotta (URL, cím,
    #: megnyitott rekord) - az "ez"/"ennél" hivatkozások alapja.
    kontextus: dict | None = None


@router.post("/beszelgetesek/{beszelgetes_id}/uzenet")
def uzenet(
    beszelgetes_id: int,
    payload: UzenetIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """Egy felhasználói üzenet + a teljes asszisztens-kör (többlépéses
    végrehajtás). Szinkron fut; a folyamat-események közben is olvashatók a
    /uzenetek végponton (a felület pollozza)."""
    b = _sajat_beszelgetes(db, user, beszelgetes_id)
    if b.fut:
        raise HTTPException(status_code=409, detail="Ebben a beszélgetésben már fut egy kör - várd meg a végét, vagy állítsd le.")
    szoveg = payload.szoveg.strip()
    if not szoveg:
        raise HTTPException(status_code=400, detail="Üres üzenet.")

    fajl_nevek = [
        f.fajl_nev
        for f in db.scalars(select(AiFajl).where(AiFajl.beszelgetes_id == b.id, AiFajl.felhasznalva.is_(None)))
    ]
    # Az oldal-kontextus is az üzenetre kerül: ebből látja Lara (lásd
    # admin_agent/asszisztens.py), melyik oldalról kérdeztek.
    adat: dict = {}
    if fajl_nevek:
        adat["fajlok"] = fajl_nevek
    if isinstance(payload.kontextus, dict) and payload.kontextus:
        adat["kontextus"] = {k: v for k, v in payload.kontextus.items() if isinstance(v, (str, int, float, bool))}
    felhasznaloi = AiUzenet(
        beszelgetes_id=b.id,
        szerep="felhasznalo",
        szoveg=szoveg,
        adat=adat or None,
    )
    db.add(felhasznaloi)
    if not b.cim:
        b.cim = szoveg[:120]
    b.fut = True
    b.leallitas_kert = False
    db.commit()
    utolso_elotti = felhasznaloi.id

    try:
        ai_assistant.futtat(db, user, b, szoveg, kontextus=payload.kontextus)
    finally:
        db.rollback()
        b = db.get(AiBeszelgetes, beszelgetes_id)
        if b is not None:
            b.fut = False
            db.commit()

    ujak = db.scalars(
        select(AiUzenet).where(AiUzenet.beszelgetes_id == beszelgetes_id, AiUzenet.id >= utolso_elotti).order_by(AiUzenet.id)
    ).all()
    return {"uzenetek": [UzenetOut.model_validate(u) for u in ujak]}


@router.post("/beszelgetesek/{beszelgetes_id}/leallitas")
def leallitas(
    beszelgetes_id: int, db: Session = Depends(get_db), user: Employee = Depends(get_current_user)
):
    """A futó kör leállítás-kérése - a hurok a következő lépés előtt megáll,
    a már elvégzett lépések érvényben maradnak."""
    b = _sajat_beszelgetes(db, user, beszelgetes_id)
    b.leallitas_kert = True
    db.commit()
    return {"ok": True}


class DontesIn(BaseModel):
    jovahagyva: bool


@router.post("/muveletek/{muvelet_id}/dontes")
def muvelet_dontes(
    muvelet_id: int,
    payload: DontesIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """A felhasználó döntése egy függő (megerősítendő) műveletről. A
    végrehajtás PONTOSAN a tárolt kéréssel történik - a jóváhagyás arra a
    konkrét műveletre vonatkozik, amit a kártya mutatott."""
    muvelet = db.get(AiMuvelet, muvelet_id)
    if muvelet is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen művelet.")
    _sajat_beszelgetes(db, user, muvelet.beszelgetes_id)

    mar_eldontott = muvelet.allapot != "fuggo"
    eredmeny = ai_eszkozok.vegrehajt_fuggo_muveletet(db, user, muvelet, payload.jovahagyva)
    if mar_eldontott:
        # Ismételt kattintás/kérés: a művelet NEM futott le újra - a tárolt
        # eredmény megy vissza, a beszélgetésbe nem kerül duplikált üzenet.
        return {
            "allapot": muvelet.allapot,
            "status": muvelet.valasz_status,
            "valasz": muvelet.valasz,
            "uzenet": f"Ez a művelet már {muvelet.allapot} állapotban van - nem futott le újra.",
        }

    # Determinista visszajelzés a beszélgetésbe - nem a modell írja, tehát
    # akkor is pontos, ha a modell épp nem fut.
    if eredmeny.get("allapot") == "elutasitva":
        szoveg = f"Elvetetted a műveletet ({muvelet.osszefoglalo or muvelet.path}) - nem történt módosítás."
    elif muvelet.allapot == "vegrehajtva":
        szoveg = f"Jóváhagytad, végrehajtottam: {muvelet.osszefoglalo or muvelet.path}."
    else:
        reszlet = ""
        if isinstance(muvelet.valasz, dict) and muvelet.valasz.get("detail"):
            reszlet = f" ({muvelet.valasz['detail']})"
        szoveg = f"A jóváhagyott művelet nem sikerült: HTTP {muvelet.valasz_status}{reszlet}."
    db.add(
        AiUzenet(
            beszelgetes_id=muvelet.beszelgetes_id,
            szerep="asszisztens",
            szoveg=szoveg,
            adat={"tipus": "muvelet_eredmeny", "muvelet_id": muvelet.id, "allapot": muvelet.allapot},
        )
    )
    db.commit()
    return {
        "allapot": muvelet.allapot,
        "status": muvelet.valasz_status,
        "valasz": muvelet.valasz,
        "uzenet": szoveg,
    }


@router.get("/beszelgetesek/{beszelgetes_id}/naplo")
def muvelet_naplo(
    beszelgetes_id: int, db: Session = Depends(get_db), user: Employee = Depends(get_current_user)
):
    """A beszélgetés írás-naplója: ki, mikor, mit hívott, mi lett az eredmény
    - a sikeres és a hátralévő (függő) lépések külön látszanak."""
    b = _sajat_beszelgetes(db, user, beszelgetes_id)
    sorok = db.scalars(
        select(AiMuvelet).where(AiMuvelet.beszelgetes_id == b.id).order_by(AiMuvelet.id)
    ).all()
    return [
        {
            "id": m.id,
            "allapot": m.allapot,
            "method": m.method,
            "path": m.path,
            "osszefoglalo": m.osszefoglalo,
            "status": m.valasz_status,
            "vegrehajtva_at": m.vegrehajtva_at.isoformat() if m.vegrehajtva_at else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in sorok
    ]

