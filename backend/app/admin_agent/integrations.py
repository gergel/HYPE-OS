"""HYRON — integráció-állapot (forráskapcsolatok).

VALÓS állapotot ad vissza (nem mock): a szükséges kulcsok/konfiguráció
tényleges meglétét nézi a beállításokból. Hiányzó konfiguráció esetén az
érintett eszköz „Beállítás szükséges" állapotban marad és tiltott — a többi
rész működik tovább. A titkok ÉRTÉKE sosem kerül a válaszba, csak az állapot.
"""

from __future__ import annotations

from app.core.config import settings

KESZ = "kesz"
BEALLITAS_SZUKSEGES = "beallitas_szukseges"


def _gmail_konfiguralt() -> bool:
    return bool(
        getattr(settings, "gmail_oauth_token_json", None)
        or getattr(settings, "tigtoken_json", None)
        or getattr(settings, "gmail_service_account_json", None)
        or (
            getattr(settings, "gmail_oauth_client_id", None)
            and getattr(settings, "gmail_oauth_client_secret", None)
            and getattr(settings, "gmail_oauth_refresh_token", None)
        )
    )


def _modell_konfiguralt() -> bool:
    # A kiolvasás Geminire épül; a tervező cserélhető. Bármely ismert kulcs elég.
    for kulcs in ("gemini_api_key", "google_api_key", "gemini_api_key_json", "anthropic_api_key"):
        if getattr(settings, kulcs, None):
            return True
    return False


def _tarolo_konfiguralt() -> bool:
    # A dokumentumok a meglévő objektumtárolóra (Cloudflare R2) kerülnek.
    return bool(getattr(settings, "r2_account_id", None) and getattr(settings, "r2_access_key_id", None))


def integracio_allapotok() -> list[dict]:
    """Az egyes forráskapcsolatok állapota a felülethez. Az `eszkozok` mező
    mondja meg, mely HYRON eszközök függenek az adott integrációtól."""
    gmail = _gmail_konfiguralt()
    modell = _modell_konfiguralt()
    tarolo = _tarolo_konfiguralt()
    return [
        {
            "kulcs": "gmail",
            "nev": "Gmail (levélküldés/érkeztetés)",
            "allapot": KESZ if gmail else BEALLITAS_SZUKSEGES,
            "eszkozok": ["email.valasz_kuldes"],
            "uzenet": None
            if gmail
            else "Nincs Gmail hitelesítés beállítva (GMAIL_OAUTH_TOKEN_JSON / szolgáltatásfiók / OAuth kliens).",
        },
        {
            "kulcs": "modell",
            "nev": "Modell (kiolvasás/elemzés)",
            "allapot": KESZ if modell else BEALLITAS_SZUKSEGES,
            "eszkozok": [],
            "uzenet": None if modell else "Nincs modell API-kulcs konfigurálva (a determinista elemzés ettől még fut).",
        },
        {
            "kulcs": "tarolo",
            "nev": "Dokumentumtár",
            "allapot": KESZ if tarolo else BEALLITAS_SZUKSEGES,
            "eszkozok": [],
            "uzenet": None if tarolo else "Nincs dokumentumtár (objektumtároló) konfigurálva.",
        },
    ]


def eszkoz_elerheto(eszkoz: str) -> tuple[bool, str | None]:
    """Egy HYRON eszköz elérhető-e (a függő integráció konfigurált-e).
    Vissza: (elérhető?, indok ha nem)."""
    for i in integracio_allapotok():
        if eszkoz in i["eszkozok"] and i["allapot"] != KESZ:
            return False, i["uzenet"] or f"{i['nev']}: beállítás szükséges."
    return True, None
