"""Fázis 2, 1. kör: az önmagukban álló entitások idempotens importja Notionból.

Használat (Railway-en, `railway ssh` után, ahol a NOTION_API_KEY env var be van
állítva a backend service Variables fülén):

    python scripts/notion_import.py

Bármikor újrafuttatható - a NotionImportMap tábla (notion_page_id -> a mi entitásunk)
miatt nem duplikál, csak frissíti a már importált rekordokat.

Amit ez a script (még) NEM importál, és miért:
- 4 névre szabott elszámolás-klón (Bükfa Kristóf, Salamon Zalán, Fábián Péter, Nemes
  Attila adatbázis), 2025 CEU RecruiTECH Blue, 2025 beosztása, New form: a
  hype_os_migration_map.md döntése szerint adatmigráció nélkül törlődnek.
- Leltárak, Leltár tételek: audit-jellegű táblák, nálunk nincs önálló entitásuk.
- Stock igények, Geri elszámolás, Törölt anyagok: bonyolultabb, egyedi logikájú
  táblák - külön körben térünk vissza rájuk.
- "Kreatív team database": a discovery alapján kiderült, hogy ez valójában egy
  ügyfél-onboarding/sales pipeline tábla, NEM crew-lista (a migrációs doksi
  feltételezése ezen a ponton téves volt) - erre külön kell megoldást találni.
- "Belsős" / "Külsős": ezek TIG/számla-nyilvántartó táblák, nem employee-directory -
  az Employee-t a "Külsős és belsős" (a valódi crew-directory) tábla adja.
- Main Database + az arra épülő Project/Utómunka/Timesheet/Pénzügyek/Visszajelzés/
  Diszpó lánc: ez a 2. kör, miután ez az 1. kör lefutott és ellenőrizve lett.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.notion_import import importers  # noqa: E402
from app.notion_import.client import NotionClient  # noqa: E402
from app.notion_import.engine import run_importer  # noqa: E402

IMPORTERS = [
    ("Client+Contact", importers.import_clients_and_contacts),
    ("Employee", importers.import_employees),
    ("Rate", importers.import_rates),
    ("Equipment", importers.import_equipment),
    ("Campaign", importers.import_campaigns),
    ("Task", importers.import_tasks),
    ("Contract", importers.import_contracts),
    ("ProjectCode", importers.import_project_codes),
]


def main() -> None:
    notion = NotionClient()
    db = SessionLocal()
    try:
        print("HYPE OS - Notion import, 1. kör\n" + "=" * 40)
        for name, importer_fn in IMPORTERS:
            result = run_importer(name, db, importer_fn, notion, db)
            print(result)
            if result.errors:
                print(result.error_report())
        print("=" * 40 + "\nKész.")
    finally:
        db.close()
        notion.close()


if __name__ == "__main__":
    main()
