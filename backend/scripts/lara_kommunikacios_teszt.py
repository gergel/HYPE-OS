"""Lara 20 kötelező kommunikációs tesztje ÉLŐ modellen.

Használat (a backend mappából):
    python -m scripts.lara_kommunikacios_teszt [--csak ID,ID] [--kimenet jelentes.json]

- Modell-kulcs (GEMINI_API_KEY) nélkül NEM fut, és eredményt sem állít.
- Csak olvas: nem nyúl az adatbázishoz; a forgatókönyvek kontextusa és
  eszköz-eredménye a JSON-fájlból jön (demó adat).
- A kemény feltételeket gépileg ellenőrzi (lásd app/admin_agent/kommunikacios_teszt.py);
  a jelentésben a rubrika mezői üresek — azokat ember tölti ki mintavétellel.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.admin_agent import kommunikacios_teszt as kt
from app.core.config import settings


def _modell(rendszer: str, szoveg: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=[types.Content(role="user", parts=[types.Part(text=szoveg)])],
        config=types.GenerateContentConfig(system_instruction=rendszer, temperature=0.3, max_output_tokens=800),
    )
    return (resp.text or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csak", default="")
    ap.add_argument("--kimenet", default="")
    a = ap.parse_args()
    if not getattr(settings, "gemini_api_key", None):
        print("Nincs GEMINI_API_KEY — az élő kommunikációs teszt nem futtatható, eredmény nincs.")
        return 2
    csak = {x.strip() for x in a.csak.split(",") if x.strip()}
    adat = kt.betolt()
    jelentes = []
    for sz in adat["szenariok"]:
        if csak and sz["id"] not in csak:
            continue
        rendszer, feladat = kt.prompt(sz)
        try:
            valasz = _modell(rendszer, feladat)
        except Exception as exc:  # noqa: BLE001
            jelentes.append({"id": sz["id"], "atment": False, "hibak": [f"modellhiba: {type(exc).__name__}"]})
            continue
        e = kt.ertekel(sz, valasz)
        e["valasz"] = valasz
        e["rubrika"] = {k: None for k in adat["rubrika"]}
        jelentes.append(e)
        print(f"{'OK ' if e['atment'] else 'HIBA'} {sz['id']}: {'; '.join(e['hibak']) or '—'}")
    atment = sum(1 for e in jelentes if e["atment"])
    print(f"\n{atment}/{len(jelentes)} forgatókönyv teljesítette a kemény feltételeket.")
    if a.kimenet:
        with open(a.kimenet, "w", encoding="utf-8") as f:
            json.dump({"verzio": adat["verzio"], "eredmenyek": jelentes}, f, ensure_ascii=False, indent=1)
    return 0 if atment == len(jelentes) else 1


if __name__ == "__main__":
    sys.exit(main())
