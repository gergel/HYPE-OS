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
  "kepviselo": a partner képviselője (természetes személy neve), ha kiolvasható, különben null,
  "nyilvantartasi_szam": a partner cégjegyzék-/nyilvántartási száma, ha kiolvasható, különben null,
  "email": a partner e-mail címe, ha szerepel, különben null,
  "telefon": a partner telefonszáma, ha szerepel, különben null
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
            # SZÁNDÉKOSAN nincs se max_output_tokens, se thinking_config: a
            # szűk token-keretet a gondolkodó-tokenek ették el (üres válasz
            # jött), a thinking_budget=0-t pedig a Gemini 3-as modellek 400
            # INVALID_ARGUMENT-tel dobják vissza (élesben 3.6 fut) - mindkét
            # hibát a felhasználó jelezte. Beállítások nélkül a hívás minden
            # modell-generáción megy, a választ a _json_kiszedese türelmesen
            # értelmezi.
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as exc:  # noqa: BLE001 - a hívó emberi hibaüzenetet vár
        logger.exception("Kiadás-kiolvasás: a Gemini-hívás elhasalt")
        raise ValueError(f"A dokumentum kiolvasása nem sikerült: {exc}") from exc

    szoveg = (valasz.text or "").strip()
    adatok = _json_kiszedese(szoveg)
    if adatok is None:
        logger.warning("Kiadás-kiolvasás: nem-JSON válasz: %r", szoveg[:1000])
        raise ValueError(
            "A dokumentumból nem sikerült értelmezhető adatokat kiolvasni. Próbáld újra - "
            "ha többször is ez jön, a dokumentum lehet, hogy csak képként tartalmazza a szöveget."
        )
    return adatok


def _json_kiszedese(szoveg: str) -> dict | None:
    """A modell válaszából a JSON objektum - elnézően: a ```json kerítést és
    a köré tévedt szöveget is levágja (a response_mime_type ellenére néha
    becsúszik), a lényeg az első és az utolsó kapcsos zárójel köze."""
    if not szoveg:
        return None
    eleje, vege = szoveg.find("{"), szoveg.rfind("}")
    if eleje == -1 or vege <= eleje:
        return None
    try:
        adatok = json.loads(szoveg[eleje : vege + 1])
    except json.JSONDecodeError:
        return None
    return adatok if isinstance(adatok, dict) else None


_SZAMLA_UTASITAS = """A csatolt dokumentum egy (jellemzően magyar) SZÁMLA vagy ahhoz hasonló bizonylat, amit a Hype Productions Kft. rendszerébe érkeztetünk.

Add vissza KIZÁRÓLAG ezt a JSON objektumot, más szöveg nélkül:
{
  "dokumentum_tipus": "szamla" | "elolegszamla" | "vegszamla" | "modosito" | "storno" | "dijbekero" | "egyeb",
  "szamlaszam": a számla sorszáma, ahogy a dokumentumon áll; ha nincs, null,
  "kibocsato": {"nev": ..., "adoszam": ..., "cim": ..., "bankszamlaszam": ..., "email": ...} - a SZÁMLA KIÁLLÍTÓJA (aki a pénzt kapja); a nem szereplő mezők null,
  "vevo": {"nev": ..., "adoszam": ...} - a számla VEVŐJE (aki fizet); a nem szereplő mezők null,
  "kiallitas_datuma": "YYYY-MM-DD" vagy null,
  "teljesites_datuma": "YYYY-MM-DD" vagy null (időszaknál az időszak UTOLSÓ napja, az időszakot a "teljesites_idoszak" mezőbe írd),
  "teljesites_idoszak": pl. "2026.08.01-2026.08.31", ha időszakra szól; különben null,
  "fizetesi_hatarido": "YYYY-MM-DD" vagy null,
  "netto": a nettó VÉGÖSSZEG tiszta számként (negatív is lehet, pl. sztornónál); ha nem szerepel, null,
  "afa_osszeg": az áfa összege számként vagy null,
  "brutto": a bruttó VÉGÖSSZEG számként vagy null,
  "penznem": "HUF" | "EUR" | "USD" | a számlán szereplő ISO kód,
  "afa_kulcsok": a szereplő áfakulcsok listája számként (pl. [27] vagy [27, 5]); adómentesnél [0],
  "ado_jeloles": adózási jelölés, ha van (pl. "AAM", "TAM", "fordított adózás", "alanyi adómentes"); különben null,
  "fizetesi_mod": pl. "átutalás", "készpénz", "bankkártya", ha szerepel; különben null,
  "tetelek": a tételsorok listája [{"megnevezes": ..., "mennyiseg": ..., "netto": ...}] - legfeljebb 20 tétel; ha nincs tételsor, [],
  "megjegyzes": a számlán szereplő megjegyzés/közlemény szövege röviden, ha van; különben null,
  "projektkod_hivatkozasok": a dokumentumban szereplő projektkód-szerű hivatkozások listája (pl. ["HYPE26-0291"]); ha nincs, [],
  "elozmeny_szamlaszam": módosító/sztornó/végszámlánál a HIVATKOZOTT eredeti számla sorszáma; különben null,
  "bizonytalan_mezok": azoknak a fenti mezőneveknek a listája, amiknél a kiolvasás bizonytalan (rossz minőségű szkennelés, kétértelmű adat)
}

Szabályok:
- Amit nem találsz a dokumentumban, az legyen null (üres lista a listáknál). SOHA ne találj ki adatot.
- A díjbekérő (proforma) NEM számla - a dokumentum_tipus legyen "dijbekero".
- Az összegeket NE számold újra és NE kerekítsd: pontosan azt add vissza, ami a dokumentumon áll.
- Többoldalas számlánál a VÉGÖSSZEG számít, nem az első oldal részösszege."""


def szamla_olvasd_ki(adat: bytes, mime_type: str) -> dict:
    """Egy SZÁMLA teljes érkeztetési kiolvasása (lásd services/
    szamla_erkeztetes.py) - gazdagabb, mint a kiadás-űrlap `olvasd_ki`-ja:
    számlaszám, felek, dátumok, áfa-kulcsok, tételek, hivatkozások és a
    bizonytalan mezők listája is jön. A Gemini a szöveges ÉS a szkennelt
    (képi) PDF-et, fotót is olvassa - külön OCR-lépcső nélkül."""
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
                types.Part(text=_SZAMLA_UTASITAS),
            ],
            # Lásd olvasd_ki: csak a JSON-kényszer - se token-keret, se
            # thinking-beállítás (modell-generációnként más-más hibát okoztak).
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as exc:  # noqa: BLE001 - a hívó emberi hibaüzenetet vár
        logger.exception("Számla-kiolvasás: a Gemini-hívás elhasalt")
        raise ValueError(f"A dokumentum kiolvasása nem sikerült: {exc}") from exc

    szoveg = (valasz.text or "").strip()
    adatok = _json_kiszedese(szoveg)
    if adatok is None:
        logger.warning("Számla-kiolvasás: nem-JSON válasz: %r", szoveg[:1000])
        raise ValueError(
            "A dokumentumból nem sikerült értelmezhető adatokat kiolvasni. Próbáld újra - "
            "ha többször is ez jön, a dokumentum lehet, hogy rossz minőségű."
        )
    return adatok


def _norm(szoveg: str | None) -> str:
    return " ".join((szoveg or "").lower().split())


def _adoszam_szamjegyei(adoszam: str | None) -> str:
    return "".join(ch for ch in (adoszam or "") if ch.isdigit())


def alvallalkozo_egyeztetes(db, adatok: dict):
    """A kiolvasott partnerhez tartozó MEGLÉVŐ alvállalkozó (Employee) -
    adószám szerint a legbiztosabb, különben cégnév/név egyezéssel; None, ha
    nincs találat (ilyenkor a felület ajánlja fel az új felvételét, a
    kiolvasott adatokkal előtöltve - a felhasználó kérése)."""
    from sqlalchemy import select

    from app.models.employee import Employee

    adoszam = _adoszam_szamjegyei(adatok.get("adoszam"))
    cegnev = _norm(adatok.get("megnevezes"))
    kepviselo = _norm(adatok.get("kepviselo"))

    jeloltek = db.scalars(select(Employee)).all()
    if adoszam:
        for e in jeloltek:
            if _adoszam_szamjegyei(getattr(e, "vallalkozas_adoszama", None)) == adoszam:
                return e
    if cegnev:
        for e in jeloltek:
            if _norm(getattr(e, "vallakozas_neve", None)) == cegnev or _norm(e.full_name) == cegnev:
                return e
    if kepviselo:
        for e in jeloltek:
            if _norm(e.full_name) == kepviselo:
                return e
    return None
