"""2. kör importerek: a Main Database-re (Project) és az arra épülő láncra
(Deliverable, Timesheet, Finance, Feedback) épülő entitások. Csak az 1. kör
(importers.py) sikeres lefutása után van értelme futtatni, mert ezek Client/
Employee/Campaign/ProjectCode relation-öket oldanak fel.

Amit ez a kör NEM importál, és miért:
- Callsheet <- 'Operatőri diszpó': a forrás táblában nincs relation mező a
  Main Database-hez, csak egy szabad szöveges 'Projektkód' rich_text - ennek
  string-alapú feloldása pont az a törékeny név/kód-egyeztetés lenne, amit a
  HYPE OS ki akar iktatni (lásd hype_os_railway_integracio.md 2. fejezet).
- Assignment <- 'Eszközkivitel': ugyanez a probléma - nincs relation a
  Main Database-hez, csak egy 'Projektkód' title mező.
Mindkettőt érdemesebb manuálisan vagy egy Notion-oldali relation mező
pótlása után importálni, nem force-olt szöveg-egyeztetéssel.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.feedback import Feedback
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.timesheet import Timesheet
from app.notion_import import database_ids as db_ids
from app.notion_import.client import NotionClient, as_date, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, safe_upsert, upsert
from app.notion_import.importers import _text, get_or_create_unknown_client

UNKNOWN_PROJECT_CODE_KEY = "project_code:unknown-notion-import"


def get_or_create_unknown_project_code(db: Session) -> ProjectCode:
    """Ha egy Main Database sor 'HYPE ADMIN projektkódok' relation-je nem oldható fel,
    ide kötjük a Project-et, hogy ne vesszen el az adat (Project.project_code_id NOT NULL)."""
    from sqlalchemy import select

    from app.models.notion_import import NotionImportMap

    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == UNKNOWN_PROJECT_CODE_KEY))
    if mapping:
        return db.get(ProjectCode, mapping.entity_id)
    unknown_client = get_or_create_unknown_client(db)
    project_code, _ = upsert(
        db,
        ProjectCode,
        "ProjectCode",
        UNKNOWN_PROJECT_CODE_KEY,
        {"projektkod": "ISMERETLEN-NOTION-IMPORT", "client_id": unknown_client.id},
    )
    return project_code


def import_projects(client: NotionClient, db: Session) -> ImportResult:
    """Project <- 'Main Database'. Ez a legnagyobb/legzajosabb tábla (144 mező,
    rengeteg button/formula) - csak az érdemi, adat-jellegű mezőket vesszük át.
    Crew-t (stáb) NEM tudunk hozzárendelni, mert az 'Operatőr' mező Notion
    user-people típusú, nem relation az Employee-forrás táblára."""
    result = ImportResult(entity_type="Project")
    unknown_project_code = get_or_create_unknown_project_code(db)

    for page in client.query_database(db_ids.MAIN_DATABASE):
        props = extract_properties(page)
        nev = _text(props.get("Name"))
        if not nev:
            result.skipped += 1
            continue

        project_code_id = (
            resolve_relation_id(db, "ProjectCode", props.get("HYPE ADMIN projektkódok") or [])
            or unknown_project_code.id
        )
        campaign_id = resolve_relation_id(db, "Campaign", props.get("Kampányok") or [])

        safe_upsert(
            db,
            result,
            Project,
            "Project",
            page["id"],
            {
                "nev": nev,
                "project_code_id": project_code_id,
                "campaign_id": campaign_id,
                "forgatas_datuma": as_date(props.get("Date")),
                "helyszin": _text(props.get("Helyszín")) or _text(props.get("Location")),
                "allapot": _text(props.get("Állapot")),
            },
            label=f"Project '{nev}'",
        )

    return result


def import_deliverables(client: NotionClient, db: Session) -> ImportResult:
    """Deliverable <- 'Utómunka'."""
    result = ImportResult(entity_type="Deliverable")

    for page in client.query_database(db_ids.UTOMUNKA):
        props = extract_properties(page)
        projekt_neve = _text(props.get("PROJEK NEVE"))
        if not projekt_neve:
            result.skipped += 1
            continue

        koltseg = props.get("Költség")
        safe_upsert(
            db,
            result,
            Deliverable,
            "Deliverable",
            page["id"],
            {
                "projekt_neve": projekt_neve,
                "project_code_id": resolve_relation_id(db, "ProjectCode", props.get("HYPE ADMIN projektkódok") or []),
                "project_id": resolve_relation_id(db, "Project", props.get("Forgatás") or []),
                "vago_employee_id": resolve_relation_id(db, "Employee", props.get("Vágók") or []),
                "campaign_id": resolve_relation_id(db, "Campaign", props.get("Kampányok") or []),
                "allapot": _text(props.get("Állapot")),
                "hatarido": as_date(props.get("Határidő")),
                "koltseg": koltseg if isinstance(koltseg, (int, float)) else None,
                "kesz_anyag_url": props.get("Kész anyag"),
                "nyersanyag_url": props.get("Nyersanyag"),
                "anyag_kikuldve": bool(props.get("Anyag kiküldve")),
            },
            label=f"Deliverable '{projekt_neve}'",
        )

    return result


def _import_timesheet_database(
    client: NotionClient, db: Session, database_id: str, result: ImportResult, deliverable_relation_field: str
) -> None:
    for page in client.query_database(database_id):
        props = extract_properties(page)
        employee_id = resolve_relation_id(db, "Employee", props.get("Vágó") or [])
        if employee_id is None:
            result.skipped += 1
            continue

        koltseg = props.get("Költség")
        safe_upsert(
            db,
            result,
            Timesheet,
            "Timesheet",
            page["id"],
            {
                "employee_id": employee_id,
                "deliverable_id": resolve_relation_id(db, "Deliverable", props.get(deliverable_relation_field) or []),
                "start_date": as_date(props.get("Start Date")),
                "end_date": as_date(props.get("End Date")),
                "koltseg": koltseg if isinstance(koltseg, (int, float)) else None,
                "statusz": _text(props.get("Státusz")),
                "completed": bool(props.get("Completed")),
            },
            label=f"Timesheet (employee_id={employee_id})",
        )


def import_timesheets(client: NotionClient, db: Session) -> ImportResult:
    """Timesheet <- 'Timesheet Public' + 'Timesheet Private' (a mi sémánkban nincs
    külön visibility mező, a kettő egy egységes Timesheet listába kerül)."""
    result = ImportResult(entity_type="Timesheet")
    _import_timesheet_database(client, db, db_ids.TIMESHEET_PUBLIC, result, "Utómunka_2")
    _import_timesheet_database(client, db, db_ids.TIMESHEET_PRIVATE, result, "Utómunka_1")
    return result


def import_expenses(client: NotionClient, db: Session) -> ImportResult:
    """Expense <- 'Kiadások' + 'Projekt kiadások' + 'Belsős extra kiadások'."""
    result = ImportResult(entity_type="Expense")

    for page in client.query_database(db_ids.KIADASOK):
        props = extract_properties(page)
        megnevezes = _text(props.get("Kedvezményezett"))
        if not megnevezes:
            result.skipped += 1
            continue

        tipus = "extra"
        employee_id = resolve_relation_id(db, "Employee", props.get("Külsős ") or [])
        if employee_id:
            tipus = "kulsos"
        else:
            employee_id = resolve_relation_id(db, "Employee", props.get("Belsős") or [])
            if employee_id:
                tipus = "belsos"

        brutto = props.get("Bruttó")
        safe_upsert(
            db,
            result,
            Expense,
            "Expense",
            page["id"],
            {
                "megnevezes": megnevezes,
                "employee_id": employee_id,
                "tipus": tipus,
                "netto": props.get("Nettó"),
                "brutto": brutto if isinstance(brutto, (int, float)) else None,
                "penznem": _text(props.get("Pénznem")) or "HUF",
                "kifizetes_modja": _text(props.get("Kifizetés módja")),
                "fizetes_hatarideje": as_date(props.get("Fizetési határidő")),
                "kesz": bool(props.get("Kész")),
            },
            label=f"Expense '{megnevezes}'",
        )

    for page in client.query_database(db_ids.PROJEKT_KIADASOK):
        props = extract_properties(page)
        megnevezes = _text(props.get("Kiadás megnevezése"))
        if not megnevezes:
            result.skipped += 1
            continue

        brutto = props.get("Bruttó összeg")
        safe_upsert(
            db,
            result,
            Expense,
            "Expense",
            page["id"],
            {
                "megnevezes": megnevezes,
                "project_code_id": resolve_relation_id(db, "ProjectCode", props.get("Projekt") or []),
                "employee_id": resolve_relation_id(db, "Employee", props.get("Személy") or []),
                "tipus": _text(props.get("Kiadás formája")) or "extra",
                "netto": props.get("Kiadás összege"),
                "brutto": brutto if isinstance(brutto, (int, float)) else None,
                "penznem": _text(props.get("Pénznem")) or "HUF",
            },
            label=f"Expense '{megnevezes}'",
        )

    for page in client.query_database(db_ids.BELSOS_EXTRA_KIADASOK):
        props = extract_properties(page)
        megnevezes = _text(props.get("Megnevezés")) or _text(props.get("Név"))
        if not megnevezes:
            result.skipped += 1
            continue

        safe_upsert(
            db,
            result,
            Expense,
            "Expense",
            page["id"],
            {
                "megnevezes": megnevezes,
                "project_code_id": resolve_relation_id(db, "ProjectCode", props.get("Projektkód") or []),
                "employee_id": resolve_relation_id(db, "Employee", props.get("Személy") or []),
                "tipus": "belsos",
                "netto": props.get("Összeg"),
                "fizetes_hatarideje": as_date(props.get("Kiadás időpontja")),
            },
            label=f"Expense '{megnevezes}'",
        )

    return result


def import_revenues(client: NotionClient, db: Session) -> ImportResult:
    """Revenue <- 'Bevételek'. Ha a Project Code relation nem oldható fel, a sort
    kihagyjuk (Revenue.project_code_id NOT NULL, itt nincs biztonságos fallback,
    mert a bevétel pénzügyi hovatartozása nem tippelhető)."""
    result = ImportResult(entity_type="Revenue")

    for page in client.query_database(db_ids.BEVETELEK):
        props = extract_properties(page)
        project_code_id = resolve_relation_id(db, "ProjectCode", props.get("HYPE ADMIN projektkódok") or [])
        if project_code_id is None:
            result.skipped += 1
            continue

        brutto = props.get("Bruttó")
        safe_upsert(
            db,
            result,
            Revenue,
            "Revenue",
            page["id"],
            {
                "project_code_id": project_code_id,
                "bevetel_formaja": _text(props.get("Bevétel formája")),
                "netto": props.get("Nettó"),
                "brutto": brutto if isinstance(brutto, (int, float)) else None,
                "penznem": _text(props.get("Pénznem")) or "HUF",
                "fizetes_hatarideje": as_date(props.get("Fizetési határidő")),
                "fizetes_datuma": as_date(props.get("Fizetés dátuma")),
            },
            label=f"Revenue (project_code_id={project_code_id})",
        )

    return result


def import_kp_forgalom(client: NotionClient, db: Session) -> ImportResult:
    """KpForgalom <- 'KP forgalom', a 'Projekt kiadások' relation alapján Expense-hez kötve."""
    result = ImportResult(entity_type="KpForgalom")

    for page in client.query_database(db_ids.KP_FORGALOM):
        props = extract_properties(page)
        expense_id = resolve_relation_id(db, "Expense", props.get("Projekt kiadások") or [])

        safe_upsert(
            db,
            result,
            KpForgalom,
            "KpForgalom",
            page["id"],
            {
                "expense_id": expense_id,
                "forgalom": _text(props.get("Forgalom")),
                "osszeg": props.get("Összeg"),
                "penznem": _text(props.get("Pénznem")) or "HUF",
                "legalis": _text(props.get("Legális")),
                "kiadas_datuma": as_date(props.get("Kiadás dátuma")),
            },
            label="KpForgalom",
        )

    return result


def import_feedback(client: NotionClient, db: Session) -> ImportResult:
    """Feedback <- 'Visszajelzéssek'. Ha a Deliverable relation nem oldható fel, a sort
    kihagyjuk (Feedback.deliverable_id NOT NULL)."""
    result = ImportResult(entity_type="Feedback")

    for page in client.query_database(db_ids.VISSZAJELZESSEK):
        props = extract_properties(page)
        deliverable_id = resolve_relation_id(db, "Deliverable", props.get("Utómunka_2") or [])
        if deliverable_id is None:
            result.skipped += 1
            continue

        safe_upsert(
            db,
            result,
            Feedback,
            "Feedback",
            page["id"],
            {
                "deliverable_id": deliverable_id,
                "project_id": resolve_relation_id(db, "Project", props.get("📅 Main Database") or []),
                "forgatta_employee_id": resolve_relation_id(db, "Employee", props.get("Aki forgatta") or []),
                "technikai_helyesseg": props.get("Technikai helyesség"),
                "kreativ_kepivilag": props.get("Kreatív és képivilág"),
                "nyersanyag_felhasznalhatosaga": props.get("Nyersanyag felhasználhatósága"),
                "ertekeles_kuldese": _text(props.get("Értékelés küldése")),
                "visszajelzes_szoveg": _text(props.get("Visszajelzés")),
            },
            label=f"Feedback (deliverable_id={deliverable_id})",
        )

    return result
