"""Google Naptár -> Projekt automatikus szinkron: a HYPE CALENDAR nevű Google
Naptárban létrehozott/módosított/törölt eseményeket tükrözi a `projects`
táblába (lásd app/workers/calendar_tasks.py - percenkénti Celery Beat feladat
hívja). Egy MÁSIK Google fiókhoz tartozik, mint a Gmail/Docs integráció (a
felhasználó megerősítette), ezért saját hitelesítő adatokat használ, de
ugyanazt a két hitelesítési módot támogatja (OAuth token JSON vagy service
account JSON + opcionális impersonation), mint amit a google_email.py már
bevezetett.

A Google Calendar API `syncToken` mechanizmusát használjuk (lásd
CalendarSyncState modell) - ez azt jelenti, hogy percenkénti futás mellett is
csak a ténylegesen VÁLTOZOTT eseményeket kérjük le, nem az egész naptárat.
Egy törölt naptár-esemény (`status: "cancelled"`) a hozzá tartozó Project
sor TÖRLÉSÉT váltja ki, egy szerkesztett esemény pedig felülírja a meglévő
Project releváns mezőit - ez szándékos, a felhasználó explicit kérése alapján
a naptár az "igazság forrása" ezekre a mezőkre nézve.

FONTOS: a korábban Notionból (a régi 2Sync -> Notion -> HYPE OS importon
keresztül) már behozott projekteket NEM szabad újra létrehozni, amikor
ugyanaz a naptáresemény először összefut ezzel a szinkronnal. A Notion-
importált projekteknek nincs megbízható, a Google Calendar event ID-jével
egyező mezőjük (a `Project.external_id` NEM ez - a felhasználó megerősítette,
hogy más eredetű/gyakran üres), ezért egy egyszeri, "legjobb próbálkozás"
egyeztetést végzünk NÉV + KEZDŐ DÁTUM alapján (lásd _find_unlinked_match) -
ha talál egyezést egy még nem naptárhoz-kötött projekt között, ahhoz köti a
naptáresemény ID-jét (nem hoz létre újat). Ez csak az ELSŐ alkalommal fut le
egy adott eseményhez - utána a sima ID-alapú keresés veszi át, tehát egy
esetleges téves egyeztetés hatóköre korlátozott (csak akkor fordulhat elő,
ha két különböző projektnek pontosan ugyanaz a neve ÉS kezdő dátuma).

Hitelesítő adatok (GOOGLE_CALENDAR_OAUTH_TOKEN_JSON vagy
GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON) nélkül minden hívás CalendarNotConfiguredError-t
dob - ezt csak valódi env varokkal lehet tesztelni, ebből a sandboxból nem."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.calendar_sync import CalendarSyncState
from app.models.client import Client
from app.models.project import Project
from app.models.project_code import ProjectCode

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Az első (sync_token nélküli) teljes szinkron időablaka - ezen kívüli
# eseményeket szándékosan NEM importáljuk projektként (ne öntsön el minket
# évekkel ezelőtti/távoli jövőbeli naptárbejegyzésekkel). A syncToken ezt az
# ablakot "megjegyzi" minden további inkrementális híváshoz is.
FULL_SYNC_LOOKBACK_DAYS = 14
FULL_SYNC_LOOKAHEAD_DAYS = 548  # kb. 18 hónap

PLACEHOLDER_PROJEKTKOD = "NAPTAR-IMPORT"
PLACEHOLDER_CLIENT_NEV = "Naptárból importált (rendezetlen)"


class CalendarNotConfiguredError(RuntimeError):
    """Nincs beállítva Google Naptár hitelesítés."""


class CalendarNotFoundError(RuntimeError):
    """A hitelesített fiók nem lát a megadott nevű naptárat."""


def _calendar_service():
    if settings.google_calendar_oauth_token_json:
        data = json.loads(settings.google_calendar_oauth_token_json)
        data.setdefault("token_uri", "https://oauth2.googleapis.com/token")
        creds = UserCredentials.from_authorized_user_info(data, scopes=CALENDAR_SCOPES)
        if not creds.valid:
            creds.refresh(Request())
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    if settings.google_calendar_service_account_json:
        info = json.loads(settings.google_calendar_service_account_json)
        sa = ServiceAccountCredentials.from_service_account_info(info, scopes=CALENDAR_SCOPES)
        if settings.google_calendar_impersonate_user:
            sa = sa.with_subject(settings.google_calendar_impersonate_user)
        return build("calendar", "v3", credentials=sa, cache_discovery=False)

    raise CalendarNotConfiguredError(
        "Nincs Google Naptár hitelesítés beállítva (GOOGLE_CALENDAR_OAUTH_TOKEN_JSON vagy "
        "GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON) - állítsd be a backend környezeti változóit."
    )


def _resolve_calendar_id(service) -> str:
    if settings.google_calendar_id:
        return settings.google_calendar_id

    target = settings.google_calendar_name.strip()
    page_token = None
    names_seen: list[str] = []
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for item in resp.get("items", []):
            summary = (item.get("summary") or "").strip()
            names_seen.append(summary)
            if summary == target:
                return item["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    raise CalendarNotFoundError(
        f"Nem található '{target}' nevű naptár a hitelesített Google fiók naptárai között "
        f"(elérhető naptárak: {', '.join(n for n in names_seen if n) or '(nincs egy sem)'}). "
        "Oszd meg a naptárat a hitelesítéshez használt fiókkal, vagy add meg közvetlenül a "
        "GOOGLE_CALENDAR_ID környezeti változót."
    )


def _parse_event_dates(event: dict) -> tuple[date | None, date | None]:
    start = event.get("start") or {}
    end = event.get("end") or {}

    if "date" in start:
        start_date = date.fromisoformat(start["date"])
        end_date = date.fromisoformat(end["date"]) if "date" in end else start_date
        # A Google Calendar API "end.date"-je egész napos eseményeknél
        # KIZÁRÓLAGOS (exclusive) - egy 1 napos esemény is a KÖVETKEZŐ napot
        # adja end-ként, ezért -1 nap kell, hogy a mi (befogadó/inclusive)
        # forgatas_datuma_vege szemantikánkkal egyezzen (lásd Project modell
        # kommentje és ForgatasokCalendar.tsx).
        end_date = end_date - timedelta(days=1)
        return start_date, (end_date if end_date > start_date else None)

    if "dateTime" in start:
        start_dt = datetime.fromisoformat(start["dateTime"])
        end_dt = datetime.fromisoformat(end["dateTime"]) if "dateTime" in end else start_dt
        start_date = start_dt.date()
        end_date = end_dt.date()
        return start_date, (end_date if end_date > start_date else None)

    return None, None


def _fetch_events(service, calendar_id: str, sync_token: str | None) -> tuple[list[dict], str | None, bool]:
    """Lekéri a változott eseményeket - syncToken birtokában csak a deltát,
    egyébként egy behatárolt ablakú teljes listát (lásd modul-fejléc). Lapoz,
    amíg el nem fogynak az oldalak, és visszaadja az utolsó oldal
    nextSyncToken-jét (a Google csak az utolsó lapon adja vissza)."""
    did_full_resync = sync_token is None
    kwargs: dict = {"calendarId": calendar_id, "singleEvents": True, "showDeleted": True, "maxResults": 250}
    if sync_token:
        kwargs["syncToken"] = sync_token
    else:
        now = datetime.now(timezone.utc)
        kwargs["timeMin"] = (now - timedelta(days=FULL_SYNC_LOOKBACK_DAYS)).isoformat()
        kwargs["timeMax"] = (now + timedelta(days=FULL_SYNC_LOOKAHEAD_DAYS)).isoformat()

    events: list[dict] = []
    next_sync_token: str | None = None
    page_token: str | None = None
    while True:
        request_kwargs = dict(kwargs)
        if page_token:
            request_kwargs["pageToken"] = page_token
        try:
            resp = service.events().list(**request_kwargs).execute()
        except HttpError as exc:
            if sync_token and exc.resp.status == 410:
                # A sync token lejárt/érvénytelenné vált (Google 410 GONE) -
                # teljes újraszinkron kell, elölről.
                return _fetch_events(service, calendar_id, None)
            raise
        events.extend(resp.get("items", []))
        next_sync_token = resp.get("nextSyncToken", next_sync_token)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return events, next_sync_token, did_full_resync


def _get_or_create_placeholder_project_code(db: Session) -> ProjectCode:
    """A naptárból érkező eseménynek nincs eleve Project Code-ja (az Ügyfél/
    pénzügyi besorolás emberi döntés) - egy közös "rendezetlen" gyűjtő Project
    Code-ba kerülnek, amit admin utólag, a Projekt szerkesztésekor átsorolhat
    a valódi Project Code-ra (a projects.project_code_id NOT NULL, szükség
    van valamilyen kezdőértékre)."""
    code = db.query(ProjectCode).filter(ProjectCode.projektkod == PLACEHOLDER_PROJEKTKOD).first()
    if code is not None:
        return code
    client = db.query(Client).filter(Client.nev == PLACEHOLDER_CLIENT_NEV).first()
    if client is None:
        client = Client(nev=PLACEHOLDER_CLIENT_NEV)
        db.add(client)
        db.flush()
    code = ProjectCode(projektkod=PLACEHOLDER_PROJEKTKOD, client_id=client.id)
    db.add(code)
    db.flush()
    return code


def _find_unlinked_match(db: Session, nev: str, forgatas_datuma: date | None) -> Project | None:
    """Lásd modul-fejléc "FONTOS" bekezdése - egyszeri, név+dátum alapú
    egyeztetés a már Notionból behozott (és emiatt még google_calendar_event_id
    nélküli) projektek közül, hogy ne duplikáljunk. Csak azok a projektek
    jöhetnek szóba, amikhez MÉG nincs naptáresemény kötve."""
    if forgatas_datuma is None:
        return None
    normalized = nev.strip().casefold()
    candidates = (
        db.query(Project)
        .filter(Project.google_calendar_event_id.is_(None))
        .filter(Project.forgatas_datuma == forgatas_datuma)
        .all()
    )
    for candidate in candidates:
        if (candidate.nev or "").strip().casefold() == normalized:
            return candidate
    return None


def sync_hype_calendar(db: Session) -> dict:
    """Fő belépési pont - lásd modul-fejléc. Minden esemény-feldolgozás saját
    SAVEPOINT-ban fut (mint a Notion importnál), hogy egy hibás esemény ne
    dobja el a köteg többi, addig sikeresen feldolgozott elemét."""
    service = _calendar_service()
    calendar_id = _resolve_calendar_id(service)

    state = db.query(CalendarSyncState).filter(CalendarSyncState.calendar_id == calendar_id).first()
    if state is None:
        state = CalendarSyncState(calendar_id=calendar_id, sync_token=None)
        db.add(state)
        db.flush()

    events, next_sync_token, did_full_resync = _fetch_events(service, calendar_id, state.sync_token)

    stats = {
        "created": 0,
        "linked_existing": 0,
        "updated": 0,
        "deleted": 0,
        "skipped": 0,
        "full_resync": did_full_resync,
        "total_events": len(events),
    }
    placeholder_code_id: int | None = None

    for event in events:
        event_id = event.get("id")
        if not event_id:
            stats["skipped"] += 1
            continue
        try:
            with db.begin_nested():
                project = db.query(Project).filter(Project.google_calendar_event_id == event_id).first()

                if event.get("status") == "cancelled":
                    if project is not None:
                        db.delete(project)
                        stats["deleted"] += 1
                    else:
                        stats["skipped"] += 1
                    continue

                nev = event.get("summary") or "(névtelen esemény)"
                forgatas_datuma, forgatas_datuma_vege = _parse_event_dates(event)
                helyszin = event.get("location") or None
                leiras = event.get("description") or None

                if project is None:
                    project = _find_unlinked_match(db, nev, forgatas_datuma)
                    if project is not None:
                        project.google_calendar_event_id = event_id
                        stats["linked_existing"] += 1
                    else:
                        if placeholder_code_id is None:
                            placeholder_code_id = _get_or_create_placeholder_project_code(db).id
                        project = Project(google_calendar_event_id=event_id, project_code_id=placeholder_code_id, nev=nev)
                        db.add(project)
                        stats["created"] += 1
                else:
                    stats["updated"] += 1

                project.nev = nev
                project.forgatas_datuma = forgatas_datuma
                project.forgatas_datuma_vege = forgatas_datuma_vege
                project.helyszin = helyszin
                project.description = leiras
        except Exception:  # noqa: BLE001
            stats["skipped"] += 1
            continue

    state.sync_token = next_sync_token
    db.commit()
    return stats
