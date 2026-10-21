"""PORTÁL-NÉVJAVASLAT az elnevezési útmutató alapján (a felhasználó kérése):
az Utómunkából indított Portál-létrehozásnál a rendszer PONTOS, kifelé
mutatható nevet ajánl - a belsős elnevezés (kódok, munkacímek) helyett az
útmutató szerinti "Ügyfél – Projekt vagy esemény [– Anyagtípus]" formát.

A javaslat CSAK ELŐTÖLTÉS: a felhasználó a létrehozó ablakban látja,
átírhatja, és a Portál címe utólag is szerkeszthető (title_override).

Két út: a meglévő Gemini-integráció adja a minőségi normalizálást (magyar
általános megnevezések, ügyfélnév-felismerés); ha nincs kulcs vagy hibázik,
egy determinisztikus szabály-tisztítás fut (kódok kiszűrése, gondolatjeles
forma) - javaslat így is mindig születik."""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deliverable import Deliverable

logger = logging.getLogger(__name__)

#: Az elnevezési útmutató sűrítve (forrás: "Elnevezési útmutató - HypeClient
#: portál" dokumentum) - ez megy a modellnek rendszer-szabályként.
UTMUTATO = """A HypeClient portál elnevezési szabályai:
- Névformák: "Ügyfél – Projekt vagy esemény"; ha az anyagtípus kell a megkülönböztetéshez: "Ügyfél – Projekt vagy esemény – Anyagtípus"; ha csak ügyfél van, projekt/esemény nélkül: "Ügyfél – Médiatár".
- A kimenő név SOSEM a belsős elnevezés: belsős kódok (pl. FIC_2026, HYPE-2013, HYPE26-0291) nem szerepelhetnek benne.
- Az ügyfél mindig az egységes, megszokott nevén szerepel (pl. TE, MTE, ADAMA, Szerencsejáték Zrt.) - az ügynökség/végügyfél szerep nem a név része.
- Az elválasztó a szóközökkel körülvett gondolatjel: " – ". Ékezetes, helyes magyar írásmód.
- Az általános megnevezések magyarul (Megnyitó, Esküvő, Fotó, Werk, Timeline); a hivatalos márka- és projektnevek változatlanul maradnak.
- Dátum és státusz NEM kerül a névbe; az esemény hivatalos nevében szereplő évszám maradhat.
- Az anyagtípust csak akkor írd ki, ha tényleg segít megkülönböztetni.
- Ismert esemény nevét ne cseréld Médiatárra. Ha az ügyfél-kapcsolat bizonytalan, ne találj ki ügyfélnevet - hagyd el, és maradjon az ellenőrzött rész (pl. "Művészetek Völgye 2026").
Példák: "Kurdy Gym opening" → "Kurdy Gym – Megnyitó"; "Emma és Marci esküvő" → "Emma és Marci – Esküvő"; "Bols mixer akadémia fotózás" → "Bols – Mixer akadémia – Fotó"; "Timeline (BECCA)" → "BECCA – Timeline"; "ADAMA" → "ADAMA – Médiatár"; "Magyar Táncművészeti Egyetem – Médiatár" → "MTE – Médiatár"."""

#: Belsős kód-szerű tokenek (FIC_2026, HYPE-2013, HYPE26-0291, TESZT28-601…) -
#: a szabály-alapú tisztítás ezeket veszi ki a névből.
KOD_MINTA = re.compile(r"\b[A-Z]{2,10}\d{0,4}[-_ ]\d{2,6}(?:-\d{2,6})?\b|\b[A-Z]{2,10}[-_]\d{2,6}\b")


def kontekstus(deliverable: Deliverable) -> dict:
    """A névadáshoz használható, a rendszerben MEGLÉVŐ adatok - a javaslat
    ezekből készül, kitalált adat nélkül."""
    projekt = deliverable.project
    pc = deliverable.project_code
    ugyfel = pc.client.nev if pc is not None and pc.client is not None else None
    return {
        "anyag_neve": deliverable.projekt_neve,
        "esemeny_neve": deliverable.esemeny_neve,
        "forgatas_neve": projekt.nev if projekt else None,
        "forgatas_esemenye": projekt.esemeny if projekt else None,
        "szerzodes_targya": pc.szerzodes_targya if pc else None,
        "ugyfel_nev": ugyfel,
        # Csak a kiszűréshez - a névbe SOSEM kerülhet bele.
        "belso_projektkod": deliverable.projektkod_szoveg,
    }


def _tisztitott(szoveg: str | None) -> str:
    """Belsős kódok ki, elválasztók " – "-re, felesleges szóközök össze."""
    if not szoveg:
        return ""
    t = KOD_MINTA.sub(" ", szoveg)
    t = re.sub(r"\s*[–—-]\s*", " – ", t)
    t = re.sub(r"\s*[|/]\s*", " – ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" –-_")
    return t.strip()


def szabaly_alapu(ctx: dict) -> str:
    """Determinisztikus tartalék-javaslat: a meglévő nevek tisztítása és az
    "Ügyfél – Tárgy" forma összeállítása; ha csak ügyfél van: "– Médiatár"."""
    targy = (
        _tisztitott(ctx.get("esemeny_neve"))
        or _tisztitott(ctx.get("anyag_neve"))
        or _tisztitott(ctx.get("forgatas_esemenye"))
        or _tisztitott(ctx.get("forgatas_neve"))
    )
    ugyfel = (ctx.get("ugyfel_nev") or "").strip()
    if not targy:
        return f"{ugyfel} – Médiatár" if ugyfel else "Médiatár"
    if ugyfel and not targy.lower().startswith(ugyfel.lower()):
        return f"{ugyfel} – {targy}"
    return targy


def javasolj(db: Session, deliverable: Deliverable) -> dict:
    """Névjavaslat egy Portálhoz: {"javaslat": str, "forras": "ai"|"szabaly",
    "indoklas": str|None}. Sosem dob - hibánál a szabály-alapú tartalék fut."""
    ctx = kontekstus(deliverable)
    if settings.gemini_api_key:
        try:
            javaslat = _gemini_javaslat(ctx)
            if javaslat:
                return javaslat
        except Exception:  # noqa: BLE001 - a tartalék így is ad javaslatot
            logger.exception("Portál-névjavaslat: a Gemini-hívás elhasalt - szabály-alapú tartalék fut")
    return {"javaslat": szabaly_alapu(ctx), "forras": "szabaly", "indoklas": None}


def _gemini_javaslat(ctx: dict) -> dict | None:
    from google import genai
    from google.genai import types

    from app.services.kiadas_kiolvasas import _json_kiszedese

    adatok = {k: v for k, v in ctx.items() if v}
    prompt = (
        f"{UTMUTATO}\n\n"
        "A rendszerben ezek az adatok vannak erről az anyagról (a belso_projektkod SOSEM kerülhet a névbe, "
        "csak a felismeréshez kapod):\n"
        f"{json.dumps(adatok, ensure_ascii=False)}\n\n"
        "Adj EGY pontos portál-nevet a szabályok szerint. KIZÁRÓLAG ezt a JSON objektumot add vissza:\n"
        '{"nev": "a javasolt név", "indoklas": "egy rövid mondat, miért ez"}\n'
        "Ne találj ki adatot: csak a megadott mezőkből dolgozz."
    )
    client = genai.Client(api_key=settings.gemini_api_key)
    valasz = client.models.generate_content(
        model=settings.gemini_model,
        contents=[types.Part(text=prompt)],
        # Lásd kiadas_kiolvasas.olvasd_ki: csak a JSON-kényszer.
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    adat = _json_kiszedese((valasz.text or "").strip())
    nev = (adat or {}).get("nev")
    if not nev or not str(nev).strip():
        return None
    return {"javaslat": str(nev).strip()[:255], "forras": "ai", "indoklas": (adat or {}).get("indoklas")}
