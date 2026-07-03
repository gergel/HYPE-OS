"""Project<->Equipment (Leltár) foglalások utólagos feltöltése, Notion API hívás NÉLKÜL.

A Project.leltar_notion_ids oszlop már a korábbi Notion import(ok) óta tartalmazza
a nyers Notion relation-t (a "Leltár" mezőn, a Main oldalon kereséssel/kattintással
hozzáadott eszközök page ID-jeit) - ezt csak a legutóbbi import_projects változat
oldja fel valódi Assignment sorokká (qty=1, "asset"-szerű foglalás). A már meglévő
Project sorokhoz ez utólag, KIZÁRÓLAG a Postgres-ben már ott lévő adatból
(NotionImportMap) is elvégezhető, nem kell hozzá újra lefuttatni a teljes (lassú,
hálózat-függő) importot.

Használat (Railway-en, `railway ssh` után):

    python scripts/backfill_project_equipment.py

Bármikor újrafuttatható (idempotens - nem hoz létre duplikált Assignment sort
egy már meglévő project+equipment párra)."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.equipment import Assignment  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.notion_import.engine import resolve_relation_ids  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        projects = db.scalars(select(Project)).all()
        linked_count = 0
        new_assignments = 0
        no_match = 0
        skipped = 0

        for project in projects:
            equipment_notion_ids = project.leltar_notion_ids or []
            if not equipment_notion_ids:
                skipped += 1
                continue

            equipment_ids = resolve_relation_ids(db, "Equipment", equipment_notion_ids)
            if not equipment_ids:
                no_match += 1
                print(
                    f"  [nincs találat] Project '{project.nev}' (id={project.id}): "
                    f"{len(equipment_notion_ids)} notion eszköz-id, egyik sincs importálva Equipment-ként"
                )
                continue

            already_linked = {
                a.equipment_id for a in db.scalars(select(Assignment).where(Assignment.project_id == project.id))
            }
            added_here = 0
            for equipment_id in equipment_ids:
                if equipment_id in already_linked:
                    continue
                db.add(Assignment(project_id=project.id, equipment_id=equipment_id, qty=1))
                added_here += 1

            if added_here:
                linked_count += 1
                new_assignments += added_here

        db.commit()
        print(
            f"\nKész. {linked_count} projekthez adtunk hozzá összesen {new_assignments} új eszköz-foglalást, "
            f"{no_match} projektnél volt notion eszköz-id de nincs hozzá importált Equipment, "
            f"{skipped} projektnél nem volt Leltár relation."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
