"""Fázis 2 első lépése: kilistázza a Notion API integrációval ténylegesen megosztott
összes adatbázist (név, ID, property-k neve+típusa), hogy a valós séma alapján -
nem találgatva - lehessen megírni a pontos mezőleképezést mind a 43 táblához.

Fontos: a Notion egy integráció csak azokat az adatbázisokat/oldalakat látja, amiket
KÉZZEL megosztottak vele (Notion oldalon: "..." menü -> Connections -> add az
integrációdat). Ha ez a script kevesebb adatbázist ír ki, mint a valós 43, először
ezt ellenőrizd.

Használat (Railway-en, `railway ssh` után, ahol a NOTION_API_KEY env var be van
állítva a backend service Variables fülén):

    python scripts/notion_discover.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.notion_import.client import NotionClient, database_title  # noqa: E402


def main() -> None:
    client = NotionClient()
    try:
        databases = client.search_databases()
    finally:
        client.close()

    if not databases:
        print(
            "Nulla adatbázis látszik az integrációval. Valószínűleg egyiket sem "
            "osztottad meg vele - Notionban minden releváns adatbázisnál/parent "
            "oldalnál: '...' menü -> Connections -> válaszd ki az integrációdat."
        )
        return

    print(f"{len(databases)} adatbázis látszik az integrációval:\n")
    for db in databases:
        title = database_title(db)
        db_id = db["id"]
        print(f"=== {title}  (id={db_id}) ===")
        properties = db.get("properties", {})
        for prop_name, prop_def in properties.items():
            print(f"    - {prop_name!r}: {prop_def.get('type')}")
        print()


if __name__ == "__main__":
    main()
