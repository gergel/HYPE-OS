"""Fázis 2 (docs/hype_os_build_roadmap.md): a HYPE Notion workspace idempotens
importja a HYPE OS Postgres-ébe, három körben.

Használat (Railway-en, `railway ssh` után, ahol a NOTION_API_KEY env var be van
állítva a backend service Variables fülén):

    python scripts/notion_import.py                  # teljes import (mind a 3 kör)
    python scripts/notion_import.py --only Equipment  # csak egyetlen entitás (lásd a
                                                       # lenti listákban a pontos nevet)

Bármikor újrafuttatható - a NotionImportMap tábla (notion_page_id -> a mi entitásunk)
miatt nem duplikál, csak frissíti a már importált rekordokat. A körök egymásra épülnek
(relation-feloldás), ezért teljes importnál mindig ugyanabban a sorrendben futnak, egy
futtatáson belül. A --only kapcsoló ETTŐL FÜGGETLENÜL, önmagában futtat egyetlen
importert - az Equipment ('Leltár') ehhez biztonságos, mert nem függ semmilyen más
entitás előzetes importjától (a Projektekkel/Stock igényekkel való összekötés külön,
a Project- és Stock igények-importerekben történik, nem itt).

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


ALL_IMPORTERS = WAVE_1 + WAVE_2 + WAVE_3


def run_wave(title: str, wave: list, notion: NotionClient, db) -> None:
    print(f"\n{title}\n" + "=" * 40)
    for name, importer_fn in wave:
        result = run_importer(name, db, importer_fn, notion, db)
        print(result)
        if result.errors:
            print(result.error_report())


def find_importer(name: str):
    """Ismeretlen névnél None-t ad vissza - a hívó a NotionClient() (és ezzel a
    NOTION_API_KEY-igény) ELŐTT ellenőrzi, hogy egy elgépelt --only név ne csak
    Notion-hitelesítéssel derüljön ki."""
    return next((fn for importer_name, fn in ALL_IMPORTERS if importer_name.lower() == name.lower()), None)


def run_only(name: str, importer_fn, notion: NotionClient, db) -> None:
    print(f"\nHYPE OS - Notion import, csak: {name}\n" + "=" * 40)
    result = run_importer(name, db, importer_fn, notion, db)
    print(result)
    if result.errors:
        print(result.error_report())


def main() -> None:
    only = None
    if len(sys.argv) > 1:
        if sys.argv[1] != "--only" or len(sys.argv) < 3:
            print("Használat: python scripts/notion_import.py [--only <importer neve>]")
            sys.exit(1)
        only = sys.argv[2]

    only_fn = None
    if only:
        only_fn = find_importer(only)
        if only_fn is None:
            available = ", ".join(importer_name for importer_name, _ in ALL_IMPORTERS)
            print(f"Ismeretlen importer: '{only}'.\nVálaszthatók: {available}")
            sys.exit(1)

    notion = NotionClient()
    db = SessionLocal()
    try:
        if only:
            run_only(only, only_fn, notion, db)
        else:
            run_wave("HYPE OS - Notion import, 1. kör", WAVE_1, notion, db)
            run_wave("HYPE OS - Notion import, 2. kör", WAVE_2, notion, db)
            run_wave("HYPE OS - Notion import, 3. kör", WAVE_3, notion, db)
        print("\n" + "=" * 40 + "\nKész.")
    finally:
        db.close()
        notion.close()


if __name__ == "__main__":
    main()
