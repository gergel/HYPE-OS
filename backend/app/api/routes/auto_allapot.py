"""AUTÓ ÁLLAPOTFOTÓK - a bekérő link kezelése és az autónkénti állapot oldal
(admin), valamint a link publikus feltöltő végpontjai (lásd
models/auto_allapot.py, services/auto_allapot.py).

TESZT JELLEG (a felhasználó kérése): a linket kézzel kell kiküldeni - a
diszpóval NEM megy ki automatikusan."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.routes.autok import _MINDEN_SZEREPKOR, PAGE
from app.core.database import get_db
from app.core.security import require_page_action
from app.models.auto import Auto
from app.models.auto_allapot import AutoAllapotBekeres, AutoAllapotFoto
from app.models.employee import Employee
from app.services import auto_allapot as szolg
from app.services.hu_datum import budapesti_ma

router = APIRouter(prefix="/autok", tags=["autok"])
public_router = APIRouter(prefix="/public/auto-allapot", tags=["auto-allapot-public"])


def _auto_vagy_404(db: Session, auto_id: int) -> Auto:
    auto = db.get(Auto, auto_id)
    if auto is None:
        raise HTTPException(status_code=404, detail="Az autó nem található.")
    return auto


def _bekeres_kimenet(b: AutoAllapotBekeres, ma) -> dict:
    return {
        "id": b.id,
        "token": b.token,
        "letrejott_at": b.letrejott_at,
        "visszavonva_at": b.visszavonva_at,
        "mai_db": sum(1 for f in b.fotok if szolg.nap(f.keszult_at) == ma),
    }


@router.get("/{auto_id}/allapot")
def auto_allapot(
    auto_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
) -> dict:
    """Az autó állapot oldala: a bekérő linkek és a fotók napokra bontva."""
    auto = _auto_vagy_404(db, auto_id)
    ma = budapesti_ma()
    bekeresek = db.scalars(
        select(AutoAllapotBekeres).where(AutoAllapotBekeres.auto_id == auto.id).order_by(AutoAllapotBekeres.id.desc())
    ).all()
    return {
        "auto": {"id": auto.id, "rendszam": auto.rendszam, "megnevezes": auto.megnevezes, "tipus": auto.tipus},
        "oldalak": szolg.oldalak(),
        "bekeresek": [_bekeres_kimenet(b, ma) for b in bekeresek],
        "napok": szolg.napok(db, auto.id),
    }


@router.post("/{auto_id}/allapot/bekeres", status_code=201)
def bekeres_letrehozasa(
    auto_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
) -> dict:
    """Új bekérő link az autóhoz. Egyelőre teszt jelleggel: a linket kézzel
    kell kiküldeni (a diszpóval nem megy ki automatikusan)."""
    auto = _auto_vagy_404(db, auto_id)
    b = AutoAllapotBekeres(auto_id=auto.id, token=szolg.uj_token(), letrehozta_id=user.id)
    db.add(b)
    db.commit()
    db.refresh(b)
    return _bekeres_kimenet(b, budapesti_ma())


@router.delete("/{auto_id}/allapot/bekeres/{bekeres_id}", status_code=204)
def bekeres_visszavonasa(
    auto_id: int,
    bekeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A link visszavonása - a vele feltöltött képek megmaradnak."""
    b = db.get(AutoAllapotBekeres, bekeres_id)
    if b is None or b.auto_id != auto_id:
        raise HTTPException(status_code=404, detail="A bekérő link nem található.")
    b.visszavonva_at = b.visszavonva_at or datetime.now(timezone.utc)
    db.commit()


@router.delete("/{auto_id}/allapot/fotok/{foto_id}", status_code=204)
def foto_torlese(
    auto_id: int,
    foto_id: int,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    f = db.get(AutoAllapotFoto, foto_id)
    if f is None or f.auto_id != auto_id:
        raise HTTPException(status_code=404, detail="A fotó nem található.")
    kulcsok = [k for k in (f.kulcs, f.belyeg_kulcs) if k]
    db.delete(f)
    db.commit()
    tasks.add_task(szolg.tarhely_takaritas, kulcsok)


# ── Publikus bekérő link ─────────────────────────────────────────────────────


def _el_bekeres(db: Session, token: str) -> AutoAllapotBekeres:
    b = db.scalar(select(AutoAllapotBekeres).where(AutoAllapotBekeres.token == token))
    if b is None or b.visszavonva_at is not None:
        raise HTTPException(status_code=404, detail="Ez a link nem él (visszavonták vagy hibás).")
    return b


@public_router.get("/{token}")
def publikus_adatok(token: str, db: Session = Depends(get_db)) -> dict:
    """Mit lát a link birtokosa: melyik autó, a hét nézet, és ami MA már
    elkészült közülük."""
    b = _el_bekeres(db, token)
    auto = db.get(Auto, b.auto_id)
    ma = budapesti_ma()
    return {
        "rendszam": auto.rendszam,
        "megnevezes": auto.megnevezes or auto.tipus,
        "ma": ma.isoformat(),
        "oldalak": szolg.oldalak(),
        "mai_fotok": szolg.mai_fotok(db, auto.id, ma),
    }


@public_router.post("/{token}/foto")
async def publikus_feltoltes(
    token: str,
    tasks: BackgroundTasks,
    oldal: str = Form(...),
    keszito: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Egy nézet fotója. Az aznapi korábbi fotót ugyanarról a nézetről
    lecseréli; a feldolgozás és a tárhelyre írás szálon fut, így a hét kép
    párhuzamosan is feltölthető."""
    b = _el_bekeres(db, token)
    data = await file.read()
    try:
        szolg.ellenoriz(oldal, data, file.content_type)
    except szolg.FotoHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    tarolt = await run_in_threadpool(szolg.tarolas, b.auto_id, oldal, data)
    foto, eldobott = szolg.rogzites(db, b, oldal, tarolt, keszito)
    db.commit()
    db.refresh(foto)
    if eldobott:
        tasks.add_task(szolg.tarhely_takaritas, eldobott)
    return szolg.foto_kimenet(foto)
