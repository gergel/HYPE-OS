"""Admin végpontok a HYPE CALENDAR naptár-szinkronhoz: a Google fiók egyszeri
összekötése ("csak jelentkezz be" OAuth folyamat, lásd services/google_oauth.py),
a szinkron kézi indítása és az állapot lekérdezése.

A kézi indítás a percenkénti Celery Beat feladat (lásd workers/calendar_tasks.py)
mellett azért hasznos, mert azonnal tesztelhető anélkül, hogy az admin megvárná
a következő automatikus futást, és akkor is ad visszajelzést, ha a Celery
worker/beat még nincs (helyesen) deployolva."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import Role, require_roles
from app.models.calendar_sync import CalendarSyncState
from app.models.employee import Employee
from app.services.google_calendar import (
    CalendarAuthError,
    CalendarNotConfiguredError,
    CalendarNotFoundError,
    sync_hype_calendar,
)
from app.services.google_oauth import (
    OAuthError,
    OAuthNotConfiguredError,
    build_auth_url,
    complete_auth,
    connection_status,
    disconnect,
)

router = APIRouter(prefix="/admin/calendar-sync", tags=["admin"])


@router.post("")
def trigger_sync(db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    try:
        return sync_hype_calendar(db)
    except (CalendarNotConfiguredError, CalendarNotFoundError, CalendarAuthError, OAuthError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/status")
def get_status(db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    states = db.query(CalendarSyncState).all()
    return {
        "connection": connection_status(db),
        "calendars": [
            {"calendar_id": s.calendar_id, "has_sync_token": s.sync_token is not None, "last_synced_at": s.updated_at}
            for s in states
        ],
    }


@router.post("/oauth/start")
def oauth_start(db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    """Visszaadja a Google bejelentkezési URL-t - a frontend erre navigál. Nem
    szerver-oldali átirányítást adunk, mert a hívás a fetch() API-n keresztül
    érkezik (Bearer tokennel), ahol egy 302-t a böngésző nem a felhasználónak,
    hanem a fetch-nek kézbesítene."""
    try:
        return {"auth_url": build_auth_url(db)}
    except OAuthNotConfiguredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/oauth/callback")
def oauth_callback(
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """A Google ide irányítja vissza a BÖNGÉSZŐT a bejelentkezés után. Itt
    szándékosan nincs `require_roles` függőség: ezt a címet nem a frontend
    hívja Bearer tokennel, hanem a Google átirányítása nyitja meg, így nincs
    nálunk hitelesítő fejléc - a kérés valódiságát a `state` igazolja (lásd
    services/google_oauth.py CSRF-bekezdés).

    Végül mindig a Beállítások oldalra térünk vissza, az eredményt query
    paraméterben átadva, hogy admin a megszokott felületen lássa a
    visszajelzést egy nyers JSON válasz helyett."""
    frontend = (settings.frontend_base_url or "").rstrip("/")
    target = f"{frontend}/beallitasok" if frontend else "/beallitasok"

    def _back(**params: str) -> RedirectResponse:
        return RedirectResponse(f"{target}?{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER)

    if error:
        return _back(calendar_auth="error", message=f"A Google megszakította a bejelentkezést: {error}")
    if not code or not state:
        return _back(calendar_auth="error", message="Hiányzó kód vagy azonosító a Google válaszában.")

    try:
        email = complete_auth(db, code=code, state=state)
    except (OAuthError, OAuthNotConfiguredError) as exc:
        return _back(calendar_auth="error", message=str(exc))
    return _back(calendar_auth="ok", account=email or "")


@router.post("/oauth/disconnect")
def oauth_disconnect(db: Session = Depends(get_db), _user: Employee = Depends(require_roles(Role.ADMIN))) -> dict:
    disconnect(db)
    return {"connected": False}
