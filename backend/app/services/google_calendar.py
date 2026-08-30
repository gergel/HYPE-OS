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

HITELESÍTÉS: az ajánlott (és adminnak legegyszerűbb) út a Beállítások oldalon
egyszer elvégzett "Csatlakozás Google fiókkal" - az így kapott refresh token
adatbázisban tárolódik és magától megújul, lásd services/google_oauth.py.
Emellett visszafelé kompatibilisen továbbra is működik a két kézzel beállított
környezeti változó (GOOGLE_CALENDAR_OAUTH_TOKEN_JSON vagy
GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON). Ha egyik sincs, minden hívás
CalendarNotConfiguredError-t dob. Valódi Google hívást csak élesben lehet
tesztelni, ebből a sandboxból nem."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.calendar_sync import CalendarSyncState
from app.models.project import Project
from app.services import project_matching
from app.services.google_oauth import OAuthError, load_credentials as load_db_credentials

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Az első (sync_token nélküli) teljes szinkron időablaka - ezen kívüli
# eseményeket szándékosan NEM importáljuk projektként (ne öntsön el minket
# évekkel ezelőtti/távoli jövőbeli naptárbejegyzésekkel). A syncToken ezt az
# ablakot "megjegyzi" minden további inkrementális híváshoz is.
FULL_SYNC_LOOKBACK_DAYS = 14
FULL_SYNC_LOOKAHEAD_DAYS = 548  # kb. 18 hónap

# A naptárból érkező projektek RÉGI gyűjtő kódja ("NAPTAR-IMPORT") itt már nem
# szerepel: ma nem hozunk létre ilyet (a projekt kód nélkül is létezhet), a régi
# adatok felismerése pedig egy helyen él - services/projektkod_kotes.py.

# A Google Calendar esemény-színek (colorId) magyar nevei. A Google csak
# számot ad vissza; szín NÉLKÜLI eseménynél nincs colorId (olyankor az esemény
# a naptár alapszínét viseli, ami nem az esemény sajátja - azt nem is
# értelmezzük).
NAPTAR_SZINEK: dict[str, str] = {
    "1": "Levendula",
    "2": "Zsálya",
    "3": "Szőlő",  # a Google palettáján ez a lila árnyalat
    "4": "Flamingó",
    "5": "Banán",
    "6": "Mandarin",
    "7": "Páva",
    "8": "Grafit",
    "9": "Áfonya",
    "10": "Bazsalikom",
    "11": "Paradicsom",
}

# A SZŐLŐ színű esemény meeting / helyszínbejárás - nincs mit diszponálni
# rajta (a felhasználó szabálya). A Google palettáján a Szőlő (3) az egyetlen
# igazi lila; a Levendula (1) szándékosan NEM szerepel itt, mert az egy külön,
# világosabb szín, és egy tévesen kizárt esemény azt jelentené, hogy egy valódi
# forgatásra nem megy ki diszpó. Ha mégis kell (vagy más szín is meetinget
# jelöl), a NAPTAR_MEETING_SZINEK környezeti változóval bővíthető,
# kódmódosítás nélkül: vesszővel elválasztott Google colorId-k, pl. "1,3".
def _meeting_szinek() -> set[str]:
    nyers = (settings.naptar_meeting_szinek or "3").strip()
    return {darab.strip() for darab in nyers.split(",") if darab.strip()}


def _szin_adatok(event: dict) -> tuple[str | None, bool]:
    """(szín magyar neve, meeting-e). Szín nélküli eseménynél (None, False)."""
    color_id = event.get("colorId")
    if not color_id:
        return None, False
    color_id = str(color_id)
    return NAPTAR_SZINEK.get(color_id, f"#{color_id}"), color_id in _meeting_szinek()


class CalendarNotConfiguredError(RuntimeError):
    """Nincs beállítva Google Naptár hitelesítés."""


class CalendarNotFoundError(RuntimeError):
    """A hitelesített fiók nem lát a megadott nevű naptárat."""


class CalendarAuthError(RuntimeError):
    """A hitelesítő adatok be vannak állítva, de a Google elutasította őket
    (hibás JSON, lejárt/visszavont kulcs, hiányzó domain-wide delegation
    jóváhagyás stb.) - külön hibaosztály, hogy admin a Beállítások oldalon a
    tényleges Google hibaüzenetet lássa egy semmitmondó "szerverhiba" helyett
    (lásd main.py catch_unhandled_exceptions - enélkül minden itt eldobott
    kivétel egy generikus 500-zá silányulna, és a valódi ok csak a Railway
    logban látszana)."""


def _calendar_service(db: Session | None = None):
    try:
        # 1. Elsődleges (és ajánlott) forrás: a Beállítások oldalon egyszer
        # elvégzett "Csatlakozás Google fiókkal" után adatbázisban tárolt
        # hitelesítés - ez újul meg magától, adminnak nincs vele dolga.
        if db is not None:
            creds = load_db_credentials(db)
            if creds is not None:
                return build("calendar", "v3", credentials=creds, cache_discovery=False)

        # 2. Visszafelé kompatibilis, kézzel beállított környezeti változók.
        # A scope-ot NEM kényszerítjük rá a tárolt tokenre: ha az más
        # jogosultság-készlettel lett kiállítva, a google-auth a frissítéskor
        # elküldené ezt a listát, és a Google `invalid_scope`-pal utasítaná el.
        if settings.google_calendar_oauth_token_json:
            data = json.loads(settings.google_calendar_oauth_token_json)
            creds = UserCredentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri") or "https://oauth2.googleapis.com/token",
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
            )
            if not creds.valid:
                creds.refresh(Request())
            return build("calendar", "v3", credentials=creds, cache_discovery=False)

        if settings.google_calendar_service_account_json:
            info = json.loads(settings.google_calendar_service_account_json)
            sa = ServiceAccountCredentials.from_service_account_info(info, scopes=CALENDAR_SCOPES)
            if settings.google_calendar_impersonate_user:
                sa = sa.with_subject(settings.google_calendar_impersonate_user)
            # A service account hitelesítés csak a build() hívásnál még nem
            # derül ki, hogy tényleg működik-e - egy próba API hívással
            # (calendarList) explicit módon kikényszerítjük a tokenlekérést
            # itt, hogy a hiba (pl. hibás private_key formázás, visszavont
            # kulcs, hiányzó domain-wide delegation jóváhagyás) egyértelmű
            # üzenettel bukjon el, ne egy később, véletlenszerű helyen.
            service = build("calendar", "v3", credentials=sa, cache_discovery=False)
            service.calendarList().list(maxResults=1).execute()
            return service

        raise CalendarNotConfiguredError(
            "Nincs összekötve Google fiók a naptár szinkronhoz - nyisd meg a Beállítások oldalt, és "
            "kattints a 'Csatlakozás Google fiókkal' gombra."
        )
    except (CalendarNotConfiguredError, OAuthError):
        # Az OAuthError már tartalmazza a valódi, admin számára értelmezhető
        # üzenetet (lásd services/google_oauth.py), nem csomagoljuk újra.
        raise
    except json.JSONDecodeError as exc:
        raise CalendarAuthError(
            f"A megadott Google hitelesítő adat nem érvényes JSON ({exc}) - ellenőrizd, hogy a teljes "
            "service account/OAuth token JSON-t hiba nélkül másoltad-e be a környezeti változóba."
        ) from exc
    except HttpError as exc:
        raise CalendarAuthError(
            f"A Google elutasította a hitelesítést (HTTP {exc.resp.status}): {exc.reason or exc}. Ellenőrizd, hogy "
            "a service account fiókkal (a JSON-ban lévő client_email) meg van-e osztva a naptár, vagy ha domain-wide "
            "delegationt használsz, jóvá van-e hagyva a Google Workspace admin konzolban a megfelelő scope-ra."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - lásd CalendarAuthError docstring: mindig kell egy érthető üzenet
        raise CalendarAuthError(f"Hiba a Google Naptár hitelesítés során: {type(exc).__name__}: {exc}") from exc


def _resolve_calendar_id(service) -> str:
    if settings.google_calendar_id:
        return settings.google_calendar_id

    target = settings.google_calendar_name.strip()
    page_token = None
    names_seen: list[str] = []
    try:
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
    except HttpError as exc:
        raise CalendarAuthError(
            f"Hiba a naptárak listázása közben (HTTP {exc.resp.status}): {exc.reason or exc}."
        ) from exc

    raise CalendarNotFoundError(
        f"Nem található '{target}' nevű naptár a hitelesített Google fiók naptárai között "
        f"(elérhető naptárak: {', '.join(n for n in names_seen if n) or '(nincs egy sem)'}). "
        "Oszd meg a naptárat a hitelesítéshez használt fiókkal, vagy add meg közvetlenül a "
        "GOOGLE_CALENDAR_ID környezeti változót."
    )


def _parse_event_dates(event: dict) -> tuple[date | None, date | None, time | None, time | None]:
    """(kezdő dátum, záró dátum, kezdő időpont, záró időpont).

    Egész napos eseménynél a két időpont None - ilyenkor a naptárban sincs
    óra:perc, és nem szabad kitalálni egyet. Időpontos eseménynél mindkettőt
    átvesszük, hogy a projekten is látszódjon, hánytól hányig tart a forgatás
    (lásd Project.forgatas_kezdes_ido/forgatas_veg_ido)."""
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
        return start_date, (end_date if end_date > start_date else None), None, None

    if "dateTime" in start:
        start_dt = datetime.fromisoformat(start["dateTime"])
        end_dt = datetime.fromisoformat(end["dateTime"]) if "dateTime" in end else start_dt
        start_date = start_dt.date()
        end_date = end_dt.date()
        return (
            start_date,
            (end_date if end_date > start_date else None),
            start_dt.time().replace(second=0, microsecond=0),
            end_dt.time().replace(second=0, microsecond=0),
        )

    return None, None, None, None


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


def _find_unlinked_match(db: Session, nev: str, forgatas_datuma: date | None) -> Project | None:
    """Lásd modul-fejléc "FONTOS" bekezdése - egyszeri, név+dátum alapú
    egyeztetés a már Notionból behozott (és emiatt még google_calendar_event_id
    nélküli) projektek közül, hogy ne duplikáljunk. Csak azok a projektek
    jöhetnek szóba, amikhez MÉG nincs naptáresemény kötve.

    A párosítás szabálya KÖZÖS a Notion importtal (lásd
    services/project_matching.py): ugyanaz a név + ugyanaz a kezdő dátum. Így
    a két irány nem tud egymástól elcsúszni - bármelyik jön előbb, a másik
    ugyanahhoz a projekthez talál oda."""
    return project_matching.azonos_forgatas(db, nev, forgatas_datuma, csak_naptar_nelkul=True)


def sync_hype_calendar(db: Session) -> dict:
    """Fő belépési pont - lásd modul-fejléc. Minden esemény-feldolgozás saját
    SAVEPOINT-ban fut (mint a Notion importnál), hogy egy hibás esemény ne
    dobja el a köteg többi, addig sikeresen feldolgozott elemét."""
    service = _calendar_service(db)
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
        # Hány esemény bizonyult meetingnek/helyszínbejárásnak a színe alapján
        # - a Beállítások oldalon látszik, hogy a szabály tényleg fog-e valamit.
        "meeting": 0,
        "full_resync": did_full_resync,
        "total_events": len(events),
    }

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
                forgatas_datuma, forgatas_datuma_vege, kezdes_ido, veg_ido = _parse_event_dates(event)
                helyszin = event.get("location") or None
                leiras = event.get("description") or None
                szin, meeting = _szin_adatok(event)

                if project is None:
                    project = _find_unlinked_match(db, nev, forgatas_datuma)
                    if project is not None:
                        project.google_calendar_event_id = event_id
                        stats["linked_existing"] += 1
                    else:
                        # Projektkód NÉLKÜL jön létre: a naptáresemény nem tudja,
                        # melyik munkához tartozik, azt ember dönti el. Korábban
                        # egy gyűjtő ("NAPTAR-IMPORT") Project Code-ba került,
                        # mert a projects.project_code_id kötelező volt - de a
                        # gyűjtő nem válasz, csak egy halom: ami oda kerül, úgy
                        # néz ki, mintha el lenne intézve. A mező ma már üres is
                        # lehet (lásd services/projektkod_kotes.py), és a diszpó
                        # úgyis kéri a kódot a kiküldés előtt.
                        project = Project(google_calendar_event_id=event_id, nev=nev)
                        db.add(project)
                        stats["created"] += 1
                else:
                    stats["updated"] += 1

                project.nev = nev
                project.forgatas_datuma = forgatas_datuma
                # A tól-ig VÉGÉT csak akkor írjuk felül, ha a naptár-esemény
                # tényleg több napos. Egynapos eseménynél NEM töröljük a már
                # meglévő véget: a 2Sync a Notion több napos forgatásait
                # gyakran egynapos naptár-tükörként hozza létre, és e védelem
                # nélkül a percenkénti szinkron kitörölte a Notion-importból
                # (vagy kézi szerkesztésből) származó forgatas_datuma_vege-t -
                # így több napos forgatás sosem maradt több napos (a
                # felhasználó 2026-08-30-i hibajelzése; a Notion-import felőli
                # párja: notion_import/importers_wave2.NAPTAR_SAJAT_MEZOK).
                # Kivétel: ha az esemény kezdete a régi vég UTÁN-ra került, a
                # megőrzött vég értelmetlenné vált - azt töröljük. Több
                # naposról EGYNAPOSRA rövidíteni ezért a HYPE OS felületén
                # (vagy a kezdő dátum áthelyezésével) lehet.
                if forgatas_datuma_vege is not None:
                    project.forgatas_datuma_vege = forgatas_datuma_vege
                elif project.forgatas_datuma_vege is not None and (
                    forgatas_datuma is None or project.forgatas_datuma_vege <= forgatas_datuma
                ):
                    project.forgatas_datuma_vege = None
                project.forgatas_kezdes_ido = kezdes_ido
                project.forgatas_veg_ido = veg_ido
                project.helyszin = helyszin
                project.description = leiras
                project.naptar_szin = szin
                # A lila esemény meeting/helyszínbejárás - nincs mit diszponálni.
                # Csak akkor állítjuk vissza False-ra, ha az esemény KAPOTT
                # színt a naptárban: egy szín nélküli eseménynél nem tudunk
                # semmit, és nem írhatjuk felül a kézzel beállított jelölést.
                if szin is not None:
                    project.nem_diszponalando = meeting
                if meeting:
                    stats["meeting"] += 1
        except Exception:  # noqa: BLE001
            stats["skipped"] += 1
            continue

    state.sync_token = next_sync_token
    db.commit()
    return stats
