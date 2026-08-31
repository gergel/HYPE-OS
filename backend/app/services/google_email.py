"""Gmail küldés - a felhasználó által csatolt 'diszpo-kuldes' Railway program
(app/email_gmail.py) email-küldő rétegének portolása. Három hitelesítési mód
támogatott (Service Account domain-wide delegation, teljes OAuth token JSON,
vagy OAuth "hármas" client_id/secret/refresh_token) - amelyik env var készlet
ki van töltve, azt használjuk.

Hitelesítő adatok (GMAIL_SENDER + GMAIL_SERVICE_ACCOUNT_JSON/GMAIL_OAUTH_*)
nélkül minden hívás RuntimeError-t dob - ezt csak Railway-en, a valódi env
varokkal lehet tesztelni, ebből a sandboxból nem."""

from __future__ import annotations

import base64
import json
import logging
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]
#: A fiókban BEÁLLÍTOTT aláírás kiolvasásához kell (users.settings.sendAs.get).
#: Külön lista, mert service accountnál a kért scope-ok a token-kérésbe mennek:
#: ha ez a scope nincs engedélyezve a domain-wide delegationben, a kérés
#: elhasal - és azt nem viheti magával a KÜLDÉST is (lásd alairas_html).
SETTINGS_SCOPES = [*GMAIL_SCOPES, "https://www.googleapis.com/auth/gmail.settings.basic"]


def _gmail_service(scopes: list[str] | None = None):
    # A TIGTOKEN_JSON a különálló belsős-TIG program token-neve - azért
    # fogadjuk el, hogy a HYPE OS ugyanazzal a Railway beállítással működjön.
    scopes = scopes or GMAIL_SCOPES
    token_json = settings.gmail_oauth_token_json or settings.tigtoken_json
    if token_json:
        data = json.loads(token_json)
        data.setdefault("token_uri", "https://oauth2.googleapis.com/token")
        creds = UserCredentials.from_authorized_user_info(data, scopes=scopes)
        if not creds.valid:
            creds.refresh(Request())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    if settings.gmail_service_account_json:
        info = json.loads(settings.gmail_service_account_json)
        sa = ServiceAccountCredentials.from_service_account_info(info, scopes=scopes)
        if settings.gmail_impersonate_user:
            sa = sa.with_subject(settings.gmail_impersonate_user)
        return build("gmail", "v1", credentials=sa, cache_discovery=False)

    if settings.gmail_oauth_client_id and settings.gmail_oauth_client_secret and settings.gmail_oauth_refresh_token:
        creds = UserCredentials(
            None,
            refresh_token=settings.gmail_oauth_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.gmail_oauth_client_id,
            client_secret=settings.gmail_oauth_client_secret,
            scopes=scopes,
        )
        if not creds.valid:
            creds.refresh(Request())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    raise RuntimeError(
        "Nincs Gmail hitelesítés beállítva (GMAIL_SERVICE_ACCOUNT_JSON / GMAIL_OAUTH_TOKEN_JSON / "
        "GMAIL_OAUTH_CLIENT_ID+SECRET+REFRESH_TOKEN) - állítsd be a backend környezeti változóit."
    )


def _format_sender(sender_name: str | None = None, sender_email: str | None = None) -> str:
    """A From fejléc értéke: "Megjelenő Név <cim@domain>".

    formataddr-ral építjük, mert a megjelenő név ékezetes lehet (pl. "HYPE
    GYÁRTÁS"), és egy sima f-string esetén a Python az EGÉSZ fejlécet - a
    címet is beleértve - egyetlen =?utf-8?b?...?= blokká kódolja, amiből a
    levelezők már nem tudják kiolvasni a feladó címét. A formataddr csak a
    nevet kódolja, a <cim> érintetlen marad.

    A sender_name felülírja a globális GMAIL_SENDER_NAME-et (a diszpó pl. a
    saját nevén megy ki, lásd services/dispo.py).

    A sender_email a küldő CÍMET írja felül (alapból GMAIL_SENDER). Ezt csak
    ott használjuk, ahol a levél szándékosan más fiók nevében megy - a
    szerződésmódosítás az admin címről (lásd config.modositas_sender). A Gmail
    csak akkor engedi, ha a cím a küldő fiók saját címe vagy felvett álneve
    (send-as alias); egyébként a küldés hibára fut, és a hívó ezt kapja meg."""
    cim = (sender_email or settings.gmail_sender or "").strip()
    if not cim:
        raise RuntimeError("GMAIL_SENDER nincs beállítva.")
    name = sender_name or settings.gmail_sender_name
    if name:
        return formataddr((name, cim), charset="utf-8")
    return cim


def _sendas_beallitas(cim: str) -> dict | None:
    """A fiókban BEÁLLÍTOTT feladó-adatok (aláírás, megjelenő név) egy címhez.

    Kétszer próbálkozunk: előbb a szokásos scope-okkal (a gmail.readonly a
    beállítások olvasására is jó szokott lenni), utána a settings.basic
    scope-pal. Ha egyik sem megy - mert a token nem kapta meg a jogot, vagy a
    cím nincs felvéve a fiókban -, `None`-nal térünk vissza: a levél attól még
    kimegy, csak a beépített aláírás kerül rá. Egy hiányzó aláírás nem ér
    annyit, hogy egy kiküldés elhasaljon rajta."""
    for scopes in (None, SETTINGS_SCOPES):
        try:
            svc = _gmail_service(scopes)
            return svc.users().settings().sendAs().get(userId="me", sendAsEmail=cim).execute()
        except Exception:  # noqa: BLE001 - lásd a docstringet: ez nem hiba
            continue
    return None


def sendas_adatok(cim: str) -> tuple[str | None, str | None]:
    """(megjelenő név, aláírás HTML) a fiókban beállított feladó-adatokból.

    Egy hívás, két érték - szándékosan együtt, mert ugyanaz az egy API-kérés
    adja mindkettőt, és külön függvényként minden kiküldés kétszer kérdezné le
    ugyanazt."""
    adat = _sendas_beallitas(cim) or {}
    nev = (adat.get("displayName") or "").strip()
    alairas = (adat.get("signature") or "").strip()
    return nev or None, alairas or None


def _extract_header(headers: list[dict], name: str) -> str | None:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _build_mime(
    *,
    html: str,
    subject: str,
    sender: str,
    to_list: list[str],
    cc_list: list[str] | None = None,
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
    csatolmanyok: list[tuple[str, str, bytes]] | None = None,
    in_reply_to: str | None = None,
) -> dict:
    msg = MIMEMultipart()
    msg.attach(MIMEText(html, "html", "utf-8"))

    if pdf_bytes:
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename or "diszpo.pdf"}"')
        msg.attach(part)

    # További, a felhasználó által feltöltött csatolmányok (fájlnév, MIME típus,
    # tartalom) - pl. a diszpóhoz csatolni való dokumentumok.
    for fajlnev, content_type, adat in csatolmanyok or []:
        fotipus, _, altipus = (content_type or "application/octet-stream").partition("/")
        part = MIMEBase(fotipus or "application", altipus or "octet-stream")
        part.set_payload(adat)
        encoders.encode_base64(part)
        # A fájlnév ékezetes/szóközös is lehet - a Header-kódolást az
        # email csomagra bízzuk, hogy a levelezőben a valódi név látszódjon.
        part.add_header("Content-Disposition", "attachment", filename=fajlnev)
        msg.attach(part)

    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def cc_lista(to_list: list[str], extra_cc: list[str] | None) -> list[str]:
    """A levél tényleges CC listája: a HYPE_CC env fix címei + az extra címek
    (pl. a Beállításokban megadott diszpó másolat-címzettek), kisbetű-
    érzéketlenül szűrve - aki címzett vagy már CC, nem kerül fel még egyszer."""
    cc = list(settings.hype_cc_list or [])
    megvan = {c.strip().casefold() for c in cc} | {t.strip().casefold() for t in to_list}
    for cim in extra_cc or []:
        kulcs = (cim or "").strip().casefold()
        if kulcs and kulcs not in megvan:
            cc.append(cim.strip())
            megvan.add(kulcs)
    return cc


def send_message(
    to_list: list[str],
    subject: str,
    html_body: str,
    *,
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
    csatolmanyok: list[tuple[str, str, bytes]] | None = None,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    sender_name: str | None = None,
    sender_email: str | None = None,
    extra_cc: list[str] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Visszatér: (gmailThreadId, gmailMessageId, rfc822MessageId). CC mindig a
    HYPE_CC env-ben megadott lista + az extra_cc címei (kisbetű-érzéketlenül
    szűrve: aki címzett vagy már CC, az nem kerül fel még egyszer - pl. a
    Beállításokban megadott diszpó másolat-címzettek, lásd services/dispo.py).
    thread_id + in_reply_to esetén ugyanabban a Gmail szálban válaszol, nem új
    levelet indít.

    sender_name: a címzett által látott feladónév erre a levélre (alapból a
    GMAIL_SENDER_NAME). sender_email: a küldő CÍM (alapból GMAIL_SENDER) -
    lásd _format_sender."""
    svc = _gmail_service()
    sender = _format_sender(sender_name, sender_email)
    body = _build_mime(
        html=html_body,
        subject=subject,
        sender=sender,
        to_list=to_list,
        cc_list=cc_lista(to_list, extra_cc),
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
        csatolmanyok=csatolmanyok,
        in_reply_to=in_reply_to,
    )
    if thread_id:
        body["threadId"] = thread_id

    try:
        r = svc.users().messages().send(userId="me", body=body).execute()
    except Exception as exc:  # noqa: BLE001
        # A leggyakoribb ok, ha eltérő feladó-címmel küldünk: a Gmail csak a
        # fiók saját címét vagy felvett álnevét engedi From-nak. A nyers
        # HttpError-ból ez nem derül ki, ezért mondjuk meg, mit kell tenni.
        if sender_email and sender_email.strip().lower() != (settings.gmail_sender or "").strip().lower():
            raise RuntimeError(
                f"A Gmail nem engedte a küldést a(z) {sender_email} címről. Ez a cím a küldő fiókban "
                "legyen felvéve álnévként (Gmail → Beállítások → Fiókok → Küldés mint), vagy állítsd "
                f"át a MODOSITAS_SENDER környezeti változót. A Gmail hibája: {exc}"
            ) from exc
        raise
    thr = r.get("threadId")
    mid = r.get("id")

    # A levél EKKOR MÁR KIMENT. Ami innentől jön (a Message-Id kiolvasása a
    # szálba-válaszoláshoz), az csak kényelmi ráadás - ha ez a második Gmail
    # hívás hibázik (átmeneti hiba, rate limit), attól a küldés még sikeres,
    # és a hívónak ezt SIKERKÉNT kell látnia, különben a "Kiküldve" állapot
    # sosem íródna be egy ténylegesen kiment levél után.
    rfc822 = None
    if mid:
        try:
            meta = svc.users().messages().get(
                userId="me", id=mid, format="metadata", metadataHeaders=["Message-Id"]
            ).execute()
            headers = (meta.get("payload") or {}).get("headers") or []
            rfc822 = _extract_header(headers, "Message-Id")
        except Exception:  # noqa: BLE001 - a kiment levelet nem buktathatja meg
            logger.exception("A kiküldött levél Message-Id-jét nem sikerült kiolvasni (a levél kiment).")

    return thr, mid, rfc822


def search_thread_by_subject(subject: str) -> str | None:
    svc = _gmail_service()
    res = svc.users().threads().list(userId="me", q=f'subject:"{subject}"', maxResults=1).execute()
    threads = res.get("threads") or []
    return threads[0].get("id") if threads else None
