"""Admin-only végpont a Notion import elindításához a böngészőből, `railway
ssh` nélkül - lásd app/notion_import/run_all.py docstringjét arról, miért kellett
ez: a `railway ssh` kapcsolat rendszeresen megszakad, mielőtt a (Notion API
rate-limitje miatt akár órákig tartó) import lefutna, és a megszakadt SSH-val
együtt a benne futó Python-processz is leáll. Ez a végpont ehelyett egy
háttérszálon indítja el az importot a Railway-en éppen FUTÓ backend service
saját processzében - ez a szál a HTTP-válasz elküldése (és a kliens
lecsatlakozása) után is tovább fut, egészen addig, amíg maga a szolgáltatás
processze fut (redeploy/újraindítás esetén viszont, mint minden
memóriabeli állapot, ez is elvész - lásd _STATE)."""

import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import SessionLocal
from app.core.security import Role, require_roles
from app.models.employee import Employee
from app.notion_import.run_all import run_full_import

router = APIRouter(prefix="/admin/notion-import", tags=["admin"])

# Egyszerű, folyamatban lévő processzen belüli állapot - egyszerre csak egy
# import futhat, ezt egy lock védi. Szándékosan nem perzisztens (DB-be írt):
# ez egy egyszeri, ritkán használt admin-művelet állapota, nem üzleti adat.
_STATE: dict = {"running": False, "log": [], "started_at": None, "finished_at": None, "error": None}
_LOCK = threading.Lock()
_MAX_LOG_LINES = 4000


def _append_log(line: str) -> None:
    _STATE["log"].append(line)
    if len(_STATE["log"]) > _MAX_LOG_LINES:
        _STATE["log"] = _STATE["log"][-_MAX_LOG_LINES:]


def _run_in_background() -> None:
    db = SessionLocal()
    try:
        run_full_import(db, log=_append_log)
    except Exception as exc:  # noqa: BLE001 - az admin felületen akarjuk látni a pontos hibát
        _STATE["error"] = f"{type(exc).__name__}: {exc}"
        _append_log(f"\nHIBA: {_STATE['error']}")
    finally:
        db.close()
        _STATE["running"] = False
        _STATE["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_import(_user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    with _LOCK:
        if _STATE["running"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Már fut egy Notion import.")
        _STATE.update(running=True, log=[], started_at=datetime.now(timezone.utc).isoformat(), finished_at=None, error=None)
        thread = threading.Thread(target=_run_in_background, daemon=True)
        thread.start()
    return {"started": True}


@router.get("/status")
def get_status(_user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    return {
        "running": _STATE["running"],
        "started_at": _STATE["started_at"],
        "finished_at": _STATE["finished_at"],
        "error": _STATE["error"],
        "log": _STATE["log"],
    }
