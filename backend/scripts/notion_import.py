"""Fázis 2 (docs/hype_os_build_roadmap.md): a HYPE Notion workspace idempotens
importja a HYPE OS Postgres-ébe, három körben.

Használat (Railway-en, `railway ssh` után, ahol a NOTION_API_KEY env var be van
állítva a backend service Variables fülén):

    python scripts/notion_import.py

Bármikor újrafuttatható - a NotionImportMap tábla (notion_page_id -> a mi entitásunk)
miatt nem duplikál, csak frissíti a már importált rekordokat. A körök egymásra épülnek
(relation-feloldás), ezért mindig ugyanabban a sorrendben futnak, egy futtatáson belül.

A legtöbb entitás egy `extra` JSON mezőt is kap: ez tartalmazza azokat a Notion
mezőket, amik nem kaptak saját oszlopot (jórészt Notion formula/rollup - ugyanazt a
számítást mi Python oldalon, dinamikusan végezzük el, lásd pl. ProjectCode.becsult_profit).
Semmilyen adat nem vész el, csak a ritkán használt/redundáns mezők nem kapnak külön,
tipizált oszlopot - így a séma nem dagad szét a Notion 60+ mezős tábláival.

Amit ez a script (még mindig, szándékosan) NEM importál, és miért:
- 4 névre szabott elszámolás-klón (Bükfa Kristóf, Salamon Zalán, Fábián Péter, Nemes
  Attila adatbázis), 2025 CEU RecruiTECH Blue, 2025 beosztása, New form: a
  hype_os_migration_map.md döntése szerint adatmigráció nélkül törlődnek.
- Leltárak, Leltár tételek: audit-jellegű táblák, nálunk nincs önálló entitásuk.
- "Kreatív team database": a discovery alapján kiderült, hogy ez valójában egy
  ügyfél-onboarding/sales pipeline tábla, NEM crew-lista (a migrációs doksi
  feltételezése ezen a ponton téves volt). A felhasználó döntése (2026-07-02):
  egyelőre kimarad.
- "Belsős" / "Külsős": ezek TIG/számla-nyilvántartó táblák, nem employee-directory -
  az Employee-t a "Külsős és belsős" (a valódi crew-directory) tábla adja.
- Callsheet <- 'Operatőri diszpó' és Assignment <- 'Eszközkivitel': a forrás táblákban
  nincs relation mező a Main Database-hez, csak szabad szöveges 'Projektkód'. A
  felhasználó döntése (2026-07-02): "csak tesztek voltak, nincs szükség rájuk" - kimaradnak.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.notion_import import importers, importers_wave2, importers_wave3  # noqa: E402
from app.notion_import.client import NotionClient  # noqa: E402
from app.notion_import.engine import run_importer  # noqa: E402

WAVE_1 = [
    ("Client+Contact", importers.import_clients_and_contacts),
    ("Employee", importers.import_employees),
    ("Rate", importers.import_rates),
    ("Equipment", importers.import_equipment),
    ("Campaign", importers.import_campaigns),
    ("Task", importers.import_tasks),
    ("Contract", importers.import_contracts),
    ("ProjectCode", importers.import_project_codes),
]

WAVE_2 = [
    ("Project", importers_wave2.import_projects),
    ("Deliverable", importers_wave2.import_deliverables),
    ("Timesheet", importers_wave2.import_timesheets),
    ("Expense", importers_wave2.import_expenses),
    ("Revenue", importers_wave2.import_revenues),
    ("KpForgalom", importers_wave2.import_kp_forgalom),
    ("Feedback", importers_wave2.import_feedback),
]

WAVE_3 = [
    ("Assignment (Stock igények)", importers_wave3.import_stock_igenyek),
    ("Expense (Geri elszámolás)", importers_wave3.import_geri_elszamolas),
    ("Media (Törölt anyagok)", importers_wave3.import_torolt_anyagok),
]


def run_wave(title: str, wave: list, notion: NotionClient, db) -> None:
    print(f"\n{title}\n" + "=" * 40)
    for name, importer_fn in wave:
        result = run_importer(name, db, importer_fn, notion, db)
        print(result)
        if result.errors:
            print(result.error_report())


def main() -> None:
    notion = NotionClient()
    db = SessionLocal()
    try:
        run_wave("HYPE OS - Notion import, 1. kör", WAVE_1, notion, db)
        run_wave("HYPE OS - Notion import, 2. kör", WAVE_2, notion, db)
        run_wave("HYPE OS - Notion import, 3. kör", WAVE_3, notion, db)
        print("\n" + "=" * 40 + "\nKész.")
    finally:
        db.close()
        notion.close()


if __name__ == "__main__":
    main()
