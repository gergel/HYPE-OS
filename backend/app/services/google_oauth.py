""""Csak jelentkezz be egyszer" Google OAuth folyamat - a régi 2Sync-hez
hasonlóan adminnak nem kell se token, se service account JSON-t kézzel
környezeti változóba másolnia: a Beállítások oldalon rákattint a "Csatlakozás
Google fiókkal" gombra, bejelentkezik, és onnantól a háttérszinkron magától
fut. A Google-tól kapott refresh tokent adatbázisban tároljuk (lásd
models/google_oauth_token.py), és minden lejáráskor automatikusan megújítjuk.

MIÉRT KÉZZEL, oauthlib/Flow helyett? Két konkrét hibaforrás miatt:

1. `invalid_scope: Bad Request` - a korábbi megoldás a tárolt tokenre RÁ-
   kényszerítette a CALENDAR_SCOPES listát (`from_authorized_user_info(...,
   scopes=...)`), a google-auth pedig frissítéskor elküldi ezt a scope
   listát a Google-nek. Ha a refresh token eredetileg MÁS scope-okra lett
   kiállítva (pl. a Gmail/Docs tokent másolták be ide), a Google
   `invalid_scope`-pal utasítja el - pontosan ez a hiba látszott a felületen.
   Ezért itt a hitelesítést scope MEGADÁSA NÉLKÜL építjük fel: így a frissítés
   nem küld scope paramétert, és a Google az eredetileg megadott jogokat adja
   vissza.

2. Az oauthlib alapból hibát dob, ha a Google a kértnél több/más scope-ot ad
   vissza ("Scope has changed") - ez nálunk garantáltan előfordulna, mert az
   `openid`/`email` scope-okat a Google kibővítve (teljes URL-ként) adja
   vissza. A nyers token-csere ezt a csapdát elkerüli.

A folyamat CSRF-védelme a `pending_state`: a callbacket a BÖNGÉSZŐ hívja meg
a Google átirányítása után, ahol nincs Bearer tokenünk, ezért a "Csatlakozás"
gomb által generált, rövid életű véletlen értékkel igazoljuk, hogy a
visszatérő kérés a mi általunk indított folyamathoz tartozik."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.google_oauth_token import GoogleOAuthToken

CALENDAR_KEY = "calendar"

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"

# A naptár olvasásához kell a calendar.readonly; az email/openid csak azért,
# hogy a felületen meg tudjuk mutatni, MELYIK fiókkal van összekötve (könnyű
# elrontani, és e nélkül némán a rossz fiók naptárát szinkronizálnánk).
CALENDAR_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "openid",
    "email",
]

STATE_TTL_MINUTES = 15

#: Ennyivel a lejárat ELŐTT újítjuk meg a hozzáférést. A szinkron percekig
#: futhat; egy futás közben lejáró token fél munkával, 401-gyel állna meg.
FRISSITESI_TARTALEK = timedelta(minutes=10)


class OAuthNotConfiguredError(RuntimeError):
    """Nincs OAuth kliens (client_id/secret) beállítva - enélkül a
    "Csatlakozás Google fiókkal" gomb nem tud elindulni."""


class OAuthError(RuntimeError):
    """A Google elutasította a bejelentkezést/token-cserét - a valódi hibaüzenet
    a felületre kerül (lásd api/routes/admin_calendar_sync.py)."""


def oauth_redirect_uri() -> str:
    """A Google Cloud Console-ban ENGEDÉLYEZETT átirányítási cím. Ugyanaz az
    érték kell az auth URL-hez és a token-cseréhez is, különben a Google
    `redirect_uri_mismatch`-csel utasít el, ezért egy helyen képezzük."""
    base = (settings.api_base_url or "").rstrip("/")
    if not base:
        raise OAuthNotConfiguredError(
            "Nincs beállítva az API_BASE_URL környezeti változó - enélkül nem tudjuk megmondani a Google-nek, "
            "hova térjen vissza a bejelentkezés után. Állítsd be a backend nyilvános címére "
            "(pl. https://api.pelda.hu)."
        )
    return f"{base}/api/v1/admin/calendar-sync/oauth/callback"


def _client_credentials() -> tuple[str, str]:
    client_id = settings.calendar_oauth_client_id
    client_secret = settings.calendar_oauth_client_secret
    if not client_id or not client_secret:
        raise OAuthNotConfiguredError(
            "Nincs Google OAuth kliens beállítva. Hozz létre egyet a Google Cloud Console-ban "
            "(APIs & Services -> Credentials -> OAuth client ID -> Web application), és add meg a "
            "GOOGLE_CALENDAR_OAUTH_CLIENT_ID / GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET környezeti változókat "
            "(ha a Gmail integrációhoz már van kliensed, elég azt használni: GMAIL_OAUTH_CLIENT_ID / "
            "GMAIL_OAUTH_CLIENT_SECRET)."
        )
    return client_id, client_secret


def _expiry_from_expires_in(expires_in) -> str | None:
    """A hozzáférési token lejáratát ISO stringként tároljuk. Enélkül a
    google-auth `valid` tulajdonsága MINDIG igazat adna (lejárat hiányában nem
    tud lejártnak tekinteni egy tokent), így soha nem újítanánk meg előre - a
    percenkénti szinkron csak akkor venné észre a bajt, amikor a Google már
    401-gyel válaszol."""
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _parse_expiry(value) -> datetime | None:
    """A google-auth NAIV, UTC-ben értett datetime-ot vár a `expiry` mezőben -
    ha időzónás értéket adnánk, összehasonlításkor TypeError-t dobna."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _get_row(db: Session, key: str = CALENDAR_KEY) -> GoogleOAuthToken | None:
    return db.query(GoogleOAuthToken).filter(GoogleOAuthToken.key == key).first()


def _get_or_create_row(db: Session, key: str = CALENDAR_KEY) -> GoogleOAuthToken:
    row = _get_row(db, key)
    if row is None:
        row = GoogleOAuthToken(key=key)
        db.add(row)
        db.flush()
    return row


def build_auth_url(db: Session) -> str:
    """A "Csatlakozás Google fiókkal" gomb mögötti URL. `access_type=offline` +
    `prompt=consent` nélkül a Google MÁSODIK bejelentkezéskor már nem adna új
    refresh tokent (csak a legelsőnél), és a háttérszinkron csendben leállna,
    amint az access token lejár - ezért mindkettőt kérjük."""
    client_id, _ = _client_credentials()
    redirect_uri = oauth_redirect_uri()

    state = secrets.token_urlsafe(32)
    row = _get_or_create_row(db)
    row.pending_state = state
    row.pending_state_expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    db.commit()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(CALENDAR_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URI}?{urlencode(params)}"


def _post_token(payload: dict) -> dict:
    try:
        resp = requests.post(TOKEN_URI, data=payload, timeout=30)
    except requests.RequestException as exc:
        raise OAuthError(f"Nem sikerült elérni a Google token végpontját: {exc}") from exc
    if resp.status_code != 200:
        raise OAuthError(f"A Google elutasította a tokencserét (HTTP {resp.status_code}): {resp.text}")
    return resp.json()


def _fetch_account_email(access_token: str) -> str | None:
    """Csak kényelmi információ - ha nem sikerül, a csatlakozás attól még jó."""
    try:
        resp = requests.get(USERINFO_URI, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("email")
    except requests.RequestException:
        pass
    return None


def complete_auth(db: Session, code: str, state: str) -> str | None:
    """A Google callback feldolgozása: state-ellenőrzés, majd a kód beváltása
    refresh tokenre, amit elmentünk. A visszaadott érték a csatlakoztatott
    fiók e-mail címe (ha lekérhető)."""
    row = _get_row(db)
    if row is None or not row.pending_state:
        raise OAuthError("Nincs folyamatban lévő Google bejelentkezés - indítsd újra a csatlakoztatást.")
    if not secrets.compare_digest(row.pending_state, state):
        raise OAuthError("A Google-tól visszakapott azonosító nem egyezik - indítsd újra a csatlakoztatást.")
    expires_at = row.pending_state_expires_at
    if expires_at is not None:
        # A DB-ből naiv datetime is jöhet (ha a driver nem hozza az időzónát) -
        # ilyenkor UTC-ként kezeljük, hogy az összehasonlítás ne dobjon hibát.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise OAuthError("A bejelentkezési ablak lejárt - indítsd újra a csatlakoztatást.")

    client_id, client_secret = _client_credentials()
    data = _post_token(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": oauth_redirect_uri(),
            "grant_type": "authorization_code",
        }
    )

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise OAuthError(
            "A Google nem adott vissza refresh tokent. Vond vissza a HYPE OS hozzáférését a "
            "https://myaccount.google.com/permissions oldalon, majd csatlakoztasd újra."
        )

    access_token = data.get("access_token")
    row.token_json = json.dumps(
        {
            "type": "authorized_user",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "token": access_token,
            "expiry": _expiry_from_expires_in(data.get("expires_in")),
            "token_uri": TOKEN_URI,
        }
    )
    row.account_email = _fetch_account_email(access_token) if access_token else None
    row.pending_state = None
    row.pending_state_expires_at = None
    db.commit()
    return row.account_email


def _frissiteni_kell(creds: UserCredentials) -> bool:
    """Kell-e MOST megújítani a hozzáférést.

    Nem a lejáratig várunk, hanem `FRISSITESI_TARTALEK`-kal előbb: a szinkron
    percekig futhat, és egy futás közben lejáró token fél munkával, 401-gyel
    állna meg. A google-auth `valid` mezője csak a lejárat PILLANATÁT nézi."""
    if not creds.token:
        return True
    if creds.expiry is None:
        # Lejárat nélkül nem tudjuk, mennyi van hátra - biztosra megyünk.
        return True
    return datetime.utcnow() + FRISSITESI_TARTALEK >= creds.expiry


def _vegleges_hiba(exc: Exception) -> bool:
    """Elveszett-e VÉGLEG a hozzáférés, vagy csak most nem sikerült?

    A kettő különbsége az, hogy mit kell tenni: `invalid_grant` esetén a
    refresh token maga halott (visszavonták, lejárt, vagy jelszót cseréltek) -
    ilyenkor ÚJRA BE KELL JELENTKEZNI, és ezt ki is kell írni. Egy hálózati
    hiba viszont magától elmúlik: erre "csatlakoztasd újra a fiókot" üzenetet
    adni fölösleges riasztás, ami után valaki tényleg lecsatlakoztatja a
    működő kapcsolatot."""
    szoveg = str(exc).lower()
    return "invalid_grant" in szoveg or "invalid_client" in szoveg or "unauthorized_client" in szoveg


def _hiba_uzenet(exc: Exception) -> str:
    if _vegleges_hiba(exc):
        return (
            f"A Google visszautasította a tárolt hozzáférést ({exc}). Ez akkor történik, ha a hozzáférést "
            "visszavonták, vagy ha a Google Cloud projekt „Testing” állapotban van - ott a refresh token 7 nap "
            "után MINDIG lejár. Állítsd a projektet „In production” állapotba (OAuth consent screen -> Publish "
            "app), majd csatlakoztasd újra a fiókot a Beállítások oldalon."
        )
    return (
        f"A Google hozzáférés megújítása most nem sikerült ({type(exc).__name__}: {exc}). "
        "A tárolt hozzáférés megmarad, a következő szinkron újra próbálja."
    )


def load_credentials(db: Session) -> UserCredentials | None:
    """Az adatbázisban tárolt hitelesítés betöltése, szükség esetén
    frissítéssel. Fontos: SZÁNDÉKOSAN nem adunk meg scope-ot (lásd modul-
    fejléc 1. pont) - így a frissítés nem küld scope paramétert, és nem kaphatunk
    `invalid_scope` hibát akkor sem, ha a tokent más jogosultság-készlettel
    állították ki.

    A HOZZÁFÉRÉS NEM JÁR LE MAGÁTÓL, amíg a refresh token él: az access token
    egy órás élettartamát itt újítjuk meg, tartalékkal (lásd
    _frissiteni_kell), és minden sikeres megújítást feljegyzünk. Egy sikertelen
    megújítás NEM dobja el a tárolt hozzáférést - a hálózati hibák maguktól
    elmúlnak, és egy fél percnyi kimaradás miatt nem kell újra bejelentkezni.

    Amit viszont a kódból NEM lehet megoldani: ha a Google Cloud projekt
    „Testing” állapotban van, a Google a refresh tokent 7 naponta érvényteleníti
    - ez a beállítás dönti el, nem mi. Ezért a hibaüzenet ki is mondja."""
    row = _get_row(db)
    if row is None or not row.token_json:
        return None

    data = json.loads(row.token_json)
    creds = UserCredentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri") or TOKEN_URI,
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        expiry=_parse_expiry(data.get("expiry")),
    )

    if _frissiteni_kell(creds):
        try:
            creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001 - a valódi Google üzenet kell a felületre
            # A tárolt hozzáférést MEGTARTJUK: egy sikertelen megújítás nem
            # bizonyítja, hogy a refresh token halott. A hibát feljegyezzük,
            # hogy a Beállítások oldalon látszódjon, mióta és miért áll.
            row.last_error = _hiba_uzenet(exc)
            row.last_error_at = datetime.now(timezone.utc)
            db.commit()
            raise OAuthError(row.last_error) from exc
        # A frissített access tokent visszaírjuk, hogy a következő futásnak (és
        # a párhuzamosan futó worker folyamatnak) ne kelljen újra frissítenie.
        data["token"] = creds.token
        data["expiry"] = creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else None
        row.token_json = json.dumps(data)
        row.last_refresh_at = datetime.now(timezone.utc)
        row.last_error = None
        row.last_error_at = None
        db.commit()

    return creds


def connection_status(db: Session) -> dict:
    row = _get_row(db)
    try:
        redirect_uri = oauth_redirect_uri()
    except OAuthNotConfiguredError:
        redirect_uri = None
    return {
        "connected": bool(row and row.token_json),
        "account_email": row.account_email if row else None,
        "connected_at": row.updated_at if row and row.token_json else None,
        "client_configured": bool(settings.calendar_oauth_client_id and settings.calendar_oauth_client_secret),
        "redirect_uri": redirect_uri,
        # ÉL-E a kapcsolat, vagy csak ott áll a sorban egy halott token. A
        # tárolt hozzáférés megléte önmagában nem bizonyíték: a felület
        # korábban "Csatlakozva" állapotot mutatott olyankor is, amikor a
        # szinkron napok óta állt (lásd load_credentials).
        "last_refresh_at": row.last_refresh_at if row else None,
        "last_error": row.last_error if row else None,
        "last_error_at": row.last_error_at if row else None,
    }


def disconnect(db: Session) -> None:
    """Kapcsolat bontása - a Google oldalán is visszavonjuk a tokent (best
    effort), hogy a HYPE OS ne maradjon jogosult a fiókhoz, ha az admin
    szándékosan lecsatlakoztatta."""
    row = _get_row(db)
    if row is None:
        return
    if row.token_json:
        try:
            token = json.loads(row.token_json).get("refresh_token")
            if token:
                requests.post(REVOKE_URI, data={"token": token}, timeout=15)
        except (requests.RequestException, json.JSONDecodeError):
            pass
    row.token_json = None
    row.account_email = None
    row.pending_state = None
    row.pending_state_expires_at = None
    db.commit()
