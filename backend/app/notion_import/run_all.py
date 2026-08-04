"""A teljes (mind a 3 kör) Notion import újrafelhasználható logikája - ezt hívja
mind a `scripts/notion_import.py` CLI (railway ssh-n keresztül futtatva), mind
az admin-only `/api/v1/admin/notion-import` backend végpont (lásd
app/api/routes/admin_import.py), ami a Railway-en FUTÓ backend service saját
processzében indítja el háttérszálon - így egy megszakadt `railway ssh`
kapcsolat többé nem szakítja félbe az importot, mert nem attól a
terminálkapcsolattól függ, hanem a folyamatosan futó szolgáltatás-processztől.

A `log` paraméter absztrahálja a kimenetet: a CLI egyszerűen printeli, az admin
végpont pedig egy memóriabeli listába gyűjti (lekérdezhető állapot-lekérdezéssel),
hogy a felhasználó ssh/terminál nélkül, a böngészőből követhesse a haladást."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.notion_import import importers, importers_wave2, importers_wave3
from app.notion_import.client import NotionClient
from app.notion_import.engine import run_importer

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


def run_wave(title: str, wave: list, notion: NotionClient, db: Session, log: Callable[[str], None]) -> None:
    log(f"\n{title}\n" + "=" * 40)
    for name, importer_fn in wave:
        result = run_importer(name, db, importer_fn, notion, db)
        log(str(result))
        if result.errors or result.file_errors:
            log(result.error_report())


def find_importer(name: str):
    """Ismeretlen névnél None-t ad vissza - a hívó a NotionClient() (és ezzel a
    NOTION_API_KEY-igény) ELŐTT ellenőrzi, hogy egy elgépelt --only név ne csak
    Notion-hitelesítéssel derüljön ki."""
    return next((fn for importer_name, fn in ALL_IMPORTERS if importer_name.lower() == name.lower()), None)


def run_full_import(db: Session, log: Callable[[str], None] = print) -> None:
    notion = NotionClient()
    try:
        run_wave("HYPE OS - Notion import, 1. kör", WAVE_1, notion, db, log)
        run_wave("HYPE OS - Notion import, 2. kör", WAVE_2, notion, db, log)
        run_wave("HYPE OS - Notion import, 3. kör", WAVE_3, notion, db, log)
        log("\n" + "=" * 40 + "\nKész.")
    finally:
        notion.close()


def run_only_import(name: str, importer_fn, db: Session, log: Callable[[str], None] = print) -> None:
    notion = NotionClient()
    try:
        log(f"\nHYPE OS - Notion import, csak: {name}\n" + "=" * 40)
        result = run_importer(name, db, importer_fn, notion, db)
        log(str(result))
        if result.errors or result.file_errors:
            log(result.error_report())
        log("\n" + "=" * 40 + "\nKész.")
    finally:
        notion.close()
