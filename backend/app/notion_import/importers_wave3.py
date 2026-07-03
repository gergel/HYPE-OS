"""3. kör importerek: a maradék, egyedi logikájú táblák. Ezek is a Client/Employee/
Project/ProjectCode/Equipment relation-öket oldják fel, tehát csak az 1-2. kör
lefutása után van értelme futtatni őket."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.equipment import Assignment
from app.models.finance import Expense
from app.models.media import Media
from app.models.notion_import import NotionImportMap
from app.notion_import import database_ids as db_ids
from app.notion_import.client import NotionClient, as_date, extract_properties, remaining_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, safe_upsert, upsert
from app.notion_import.importers import _text

GERI_EMPLOYEE_KEY = "employee:geri-notion-import"


def get_or_create_geri_employee(db: Session) -> Employee:
    """A 'Geri elszámolás' Notion táblában nincs Person relation/people mező (ellentétben
    a törölt 4 klón-táblával, amiknek volt) - vagyis nem lehet megbízhatóan hozzákötni
    egy meglévő Employee-hez relation alapján, és név-egyeztetést szándékosan nem
    vezetünk be. Ezért egy jelölt placeholder Employee-t hozunk létre - ellenőrizd és
    kösd össze kézzel a valódi Geri Employee rekorddal, ha szükséges."""
    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == GERI_EMPLOYEE_KEY))
    if mapping:
        return db.get(Employee, mapping.entity_id)
    employee, _ = upsert(
        db,
        Employee,
        "Employee",
        GERI_EMPLOYEE_KEY,
        {
            "full_name": "Geri (Notion import - ellenőrizendő)",
            "tipus": EmployeeType.BELSOS,
            "role": SystemRole.OPERATOR,
            "is_active": True,
        },
    )
    return employee


_STOCK_IGENYEK_CONSUMED = {"Item", "Status", "Apply", "Qty", "Shoot", "Message", "Custom date", "Name"}


def import_stock_igenyek(client: NotionClient, db: Session) -> ImportResult:
    """Assignment <- 'Stock igények' (a darabszám-alapú, nem egyedi eszközök
    (pl. HDMI kábel) igénylése egy forgatáshoz - lásd hype_os_migration_map.md
    EQUIPMENT.track_mode="stock" logika). Ha az Item vagy a Shoot relation nem
    oldható fel, a sort kihagyjuk (Assignment mindkét FK-ja NOT NULL)."""
    result = ImportResult(entity_type="Assignment (Stock igények)")

    for page in client.query_database(db_ids.STOCK_IGENYEK):
        props = extract_properties(page, client)
        equipment_id = resolve_relation_id(db, "Equipment", props.get("Item") or [])
        project_id = resolve_relation_id(db, "Project", props.get("Shoot") or [])
        if equipment_id is None or project_id is None:
            result.skipped += 1
            continue

        qty = props.get("Qty")
        safe_upsert(
            db,
            result,
            Assignment,
            "Assignment",
            page["id"],
            {
                "equipment_id": equipment_id,
                "project_id": project_id,
                "qty": int(qty) if qty else 1,
                "kivitel_datuma": as_date(props.get("Custom date")),
                "extra": remaining_properties(props, _STOCK_IGENYEK_CONSUMED),
            },
            label=f"Assignment (stock igény, equipment_id={equipment_id})",
        )

    return result


def import_geri_elszamolas(client: NotionClient, db: Session) -> ImportResult:
    """Expense <- 'Geri elszámolás', egy jelölt Geri placeholder Employee-hez kötve
    (lásd get_or_create_geri_employee - a tábla nem hordoz Person relation-t)."""
    result = ImportResult(entity_type="Expense (Geri elszámolás)")
    geri = get_or_create_geri_employee(db)

    for page in client.query_database(db_ids.GERI_ELSZAMOLAS):
        props = extract_properties(page, client)
        megnevezes = _text(props.get("Leírás")) or "Geri elszámolás"

        netto = props.get("Kiadás összege")
        egyeb = props.get("Egyéb kiadás összege")
        if isinstance(netto, (int, float)) and isinstance(egyeb, (int, float)):
            netto = netto + egyeb
        elif isinstance(egyeb, (int, float)):
            netto = egyeb

        project_id = resolve_relation_id(db, "Project", props.get("Projektek") or [])
        project_code_id = None
        if project_id is not None:
            from app.models.project import Project

            project = db.get(Project, project_id)
            project_code_id = project.project_code_id if project else None

        safe_upsert(
            db,
            result,
            Expense,
            "Expense",
            page["id"],
            {
                "megnevezes": megnevezes,
                "employee_id": geri.id,
                "project_code_id": project_code_id,
                "tipus": _text(props.get("Kiadás tipusa")) or "geri",
                "netto": netto if isinstance(netto, (int, float)) else None,
                "fizetes_hatarideje": as_date(props.get("Kiadás dátuma")),
            },
            label=f"Expense (Geri elszámolás) '{megnevezes}'",
        )

    return result


_TOROLT_ANYAGOK_CONSUMED = {"Forgatás", "Projekt kód", "Total time", "Megrendelői kontaktok", "Name"}


def import_torolt_anyagok(client: NotionClient, db: Session) -> ImportResult:
    """Media <- 'Törölt anyagok', status='deleted' jelzéssel (lásd
    hype_os_migration_map.md: "Státusz, nem külön entitás"). Ha a 'Forgatás' relation
    nem oldható fel, a sort kihagyjuk (Media.project_id NOT NULL)."""
    result = ImportResult(entity_type="Media (Törölt anyagok)")

    for page in client.query_database(db_ids.TOROLT_ANYAGOK):
        props = extract_properties(page, client)
        title = _text(props.get("Name"))
        project_id = resolve_relation_id(db, "Project", props.get("Forgatás") or [])
        if not title or project_id is None:
            result.skipped += 1
            continue

        safe_upsert(
            db,
            result,
            Media,
            "Media",
            page["id"],
            {
                "title": title,
                "project_id": project_id,
                "storage_key": f"notion-legacy/torolt-anyagok/{page['id']}",
                "status": "deleted",
            },
            label=f"Media (törölt anyag) '{title}'",
        )

    return result
