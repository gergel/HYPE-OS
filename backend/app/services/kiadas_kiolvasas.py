"""Kiadás-adatok KIOLVASÁSA feltöltött szerződésből/számlából (a felhasználó
kérése): a PDF-et/fotót a meglévő Gemini-integráció (lásd services/
ai_assistant.py, GEMINI_API_KEY) olvassa el, és a kiadás-űrlap mezőit adja
vissza - cégnév, megnevezés, nettó összeg, ÁFA, pénznem, dátum. A kiolvasott
értékek CSAK ELŐTÖLTÉSEK: a felhasználó az űrlapon látja, javíthatja őket,
a mentés a megszokott úton megy."""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Legfeljebb ekkora fájlt olvastatunk ki - egy szerződés/számla ennél
#: kisebb; egy óriási fájl csak a kérés-időt és a tokent égetné.
MAX_MERET = 20 * 1024 * 1024

ENGEDETT_MIME = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic"}

_UTASITAS = """A csatolt dokumentum egy magyar nyelvű szerződés vagy számla, amiből egy KIADÁST vezetünk fel a Hype Productions Kft. rendszerébe (mi fizetünk valakinek).

Add vissza KIZÁRÓLAG ezt a JSON objektumot, más szöveg nélkül:
{
  "megnevezes": a PARTNER cégneve vagy neve, akinek fizetünk - szerződésnél a megbízott/vállalkozó fél, számlánál a kiállító. SOSEM a Hype Productions Kft.,
  "kiadas_leiras": mire megy a pénz - a szerződés tárgya vagy a számla fő tétele, tömören magyarul (pl. "Konferencia szervezése - SZRT Családi Nap"),
  "netto": a NETTÓ összeg tiszta számként, tagolás és pénznem nélkül (pl. 593000),
  "plusz_afa": "igen", ha az összegre ÁFA jön rá (pl. "+ÁFA", "nettó ... + ÁFA", ÁFA-s számla), különben "",
  "afa_szazalek": az ÁFA százaléka számként (ha csak "+ÁFA" szerepel konkrét százalék nélkül, akkor 27); ha nincs ÁFA, akkor null,
  "penznem": "HUF" vagy "EUR" vagy "USD",
  "kiadas_datuma": a teljesítés/esemény dátuma "YYYY-MM-DD" alakban; ha nincs, a keltezés dátuma; ha az sincs, null,
  "adoszam": a partner adószáma, ha kiolvasható, különben null,
  "szekhely": a partner székhelye, ha kiolvasható, különben null,
  "kepviselo": a partner képviselője, ha kiolvasható, különben null
}

Amit nem találsz a dokumentumban, annak az értéke legyen null. Ne találj ki adatot."""


def olvasd_ki(adat: bytes, mime_type: str) -> dict:
    """A dokumentum kiolvasása - a kiadás-űrlap mezőnevein kulcsolt dict.

    ValueError-t dob emberi hibaüzenettel (hiányzó kulcs, értelmezhetetlen
    válasz) - a végpont ezt adja tovább 4xx-ként."""
    if not settings.gemini_api_key:
        raise ValueError(
            "Az AI-kiolvasás nincs beállítva (hiányzik a GEMINI_API_KEY környezeti változó)."
        )
    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        valasz = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=adat, mime_type=mime_type),
                types.Part(text=_UTASITAS),
            ],
            # JSON-kényszer: a modell ne írjon köré magyarázó szöveget.
            config=types.GenerateContentConfig(
                response_mime_type="application/json", max_output_tokens=1024
            ),
        )
    except Exception as exc:  # noqa: BLE001 - a hívó emberi hibaüzenetet vár
        logger.exception("Kiadás-kiolvasás: a Gemini-hívás elhasalt")
        raise ValueError(f"A dokumentum kiolvasása nem sikerült: {exc}") from exc

    szoveg = (valasz.text or "").strip()
    try:
        adatok = json.loads(szoveg)
    except json.JSONDecodeError as exc:
        logger.warning("Kiadás-kiolvasás: nem-JSON válasz: %r", szoveg[:500])
        raise ValueError("A dokumentumból nem sikerült értelmezhető adatokat kiolvasni.") from exc
    if not isinstance(adatok, dict):
        raise ValueError("A dokumentumból nem sikerült értelmezhető adatokat kiolvasni.")
    return adatok
