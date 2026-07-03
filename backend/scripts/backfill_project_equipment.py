"""Project<->Equipment kapcsolat utólagos feltöltése, Notion API hívás NÉLKÜL.

A Project.kivitt_eszkozok_notion_ids / visszahozott_eszkozok_notion_ids oszlopok
már a korábbi Notion import(ok) óta tartalmazzák a nyers Notion relation-t (Equipment
page ID-k listáját) - ezt csak a legutóbbi import_projects változat oldja fel valódi
Equipment kapcsolattá (project_equipment tábla). A már meglévő Project sorokhoz ez
utólag, KIZÁRÓLAG a Postgres-ben már ott lévő adatból (NotionImportMap) is
elvégezhető, nem kell hozzá újra lefuttatni a teljes (lassú, hálózat-függő) importot.

Használat (Railway-en, `railway ssh` után):

    python scripts/backfill_project_equipment.py

Bármikor újrafuttatható (idempotens - csak felülírja a project.equipment listát a
jelenlegi notion_ids alapján, nem duplikál)."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.equipment import Equipment  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.notion_import.engine import resolve_relation_ids  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        projects = db.scalars(select(Project)).all()
        linked = 0
        no_match = 0
        skipped = 0

        for project in projects:
            equipment_notion_ids = list(
                {
                    *(project.kivitt_eszkozok_notion_ids or []),
                    *(project.visszahozott_eszkozok_notion_ids or []),
                }
            )
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

            project.equipment = db.scalars(select(Equipment).where(Equipment.id.in_(equipment_ids))).all()
            linked += 1

        db.commit()
        print(
            f"\nKész. {linked} projekt kapott eszköz-kapcsolatot, "
            f"{no_match} projektnél volt notion eszköz-id de nincs hozzá importált Equipment, "
            f"{skipped} projektnél nem volt eszköz relation."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
