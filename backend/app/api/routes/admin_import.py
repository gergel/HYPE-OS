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
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.core.security import Role, require_roles
from app.models.employee import Employee
from app.notion_import import katalogus
from app.notion_import.run_all import run_import

router = APIRouter(prefix="/admin/notion-import", tags=["admin"])

# Egyszerű, folyamatban lévő processzen belüli állapot - egyszerre csak egy
# import futhat, ezt egy lock védi. Szándékosan nem perzisztens (DB-be írt):
# ez egy egyszeri, ritkán használt admin-művelet állapota, nem üzleti adat.
_STATE: dict = {
    "running": False,
    "log": [],
    "started_at": None,
    "finished_at": None,
    "error": None,
    #: Mely adatbázisokat futtatja/futtatta az utolsó indítás (üres = mind).
    "kivalasztott": [],
}
_LOCK = threading.Lock()
_MAX_LOG_LINES = 4000


def _append_log(line: str) -> None:
    _STATE["log"].append(line)
    if len(_STATE["log"]) > _MAX_LOG_LINES:
        _STATE["log"] = _STATE["log"][-_MAX_LOG_LINES:]


def _run_in_background(nevek: list[str] | None) -> None:
    db = SessionLocal()
    try:
        run_import(db, nevek, log=_append_log)
    except Exception as exc:  # noqa: BLE001 - az admin felületen akarjuk látni a pontos hibát
        _STATE["error"] = f"{type(exc).__name__}: {exc}"
        _append_log(f"\nHIBA: {_STATE['error']}")
    finally:
        db.close()
        _STATE["running"] = False
        _STATE["finished_at"] = datetime.now(timezone.utc).isoformat()


class ImporterInfoOut(BaseModel):
    """Egy választható adatbázis a felületnek (lásd notion_import/katalogus.py)."""

    nev: str
    cimke: str
    kor: int
    forrasok: list[str]
    leiras: str
    fuggosegek: list[str]


@router.get("/importerek", response_model=list[ImporterInfoOut])
def list_importerek(_user: Employee = Depends(require_roles(Role.ADMIN))) -> list[ImporterInfoOut]:
    """Mit lehet importálni: Notion-táblánként egy sor, körrel és függőségekkel.

    A felület ebből építi a választót - így ha új importer kerül a katalógusba,
    magától megjelenik, nem kell a frontendet is módosítani."""
    return [
        ImporterInfoOut(
            nev=info.nev,
            cimke=info.cimke,
            kor=info.kor,
            forrasok=list(info.forrasok),
            leiras=info.leiras,
            fuggosegek=list(info.fuggosegek),
        )
        for info in katalogus.KATALOGUS
    ]


class ImportIndito(BaseModel):
    #: Mely adatbázisokat importáljuk. Üres/hiányzó = MINDET (a korábbi
    #: viselkedés, hogy a régi hívások változatlanul működjenek).
    importerek: list[str] | None = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_import(
    payload: ImportIndito | None = None,
    _user: Employee = Depends(require_roles(Role.ADMIN)),
) -> dict:
    """Import indítása. Megadható, mely adatbázisok fussanak; üres kéréssel
    minden fut.

    Az elgépelt nevet ITT utasítjuk vissza, nem a háttérszálban: különben a
    felhasználó csak a naplóból (vagy sehonnan) tudná meg, hogy elírta."""
    nevek = (payload.importerek if payload else None) or None
    if nevek:
        ismeretlen = katalogus.ismeretlen_nevek(nevek)
        if ismeretlen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Ismeretlen adatbázis: {', '.join(ismeretlen)}.",
            )

    with _LOCK:
        if _STATE["running"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Már fut egy Notion import.")
        kivalasztott = [info.nev for info in katalogus.valogat(nevek)]
        _STATE.update(
            running=True,
            log=[],
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
            error=None,
            kivalasztott=kivalasztott,
        )
        thread = threading.Thread(target=_run_in_background, args=(nevek,), daemon=True)
        thread.start()
    return {"started": True, "importerek": kivalasztott}


@router.get("/status")
def get_status(_user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    return {
        "running": _STATE["running"],
        "started_at": _STATE["started_at"],
        "finished_at": _STATE["finished_at"],
        "error": _STATE["error"],
        "kivalasztott": _STATE["kivalasztott"],
        "log": _STATE["log"],
    }
