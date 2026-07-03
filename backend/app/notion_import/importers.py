"""1. kör importerek: az önmagukban álló entitások, amik nem függenek a Main Database
(Project/Deliverable) feldolgozásától. Lásd scripts/notion_import.py a futtatási sorrendhez.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.client import Client, Contact
from app.models.contract import Contract, ContractType
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.equipment import Equipment, TrackMode
from app.models.campaign import Campaign
from app.models.project_code import ProjectCode
from app.models.rate import Rate
from app.models.task import Task
from app.notion_import import database_ids as db_ids
from app.notion_import.client import NotionClient, as_date, extract_properties, remaining_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, safe_upsert, upsert

UNKNOWN_CLIENT_KEY = "client:unknown-notion-import"


def _first_url(files: list | None) -> str | None:
    return files[0] if files else None


def _text(value) -> str | None:
    """Üres string helyett None-t ad vissza, hogy ne írjunk felül értelmes mezőket üressel."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def resolve_client_via_contact(db: Session, notion_contact_page_ids: list[str]) -> int | None:
    """A Client entitás szintetikus kulccsal (cég szerint csoportosítva) jön létre, nem
    1:1 egy Notion page-dzsel - ezért a 'Megrendelői kontaktok'/'Akivel szerződünk' relation
    mezők NEM Client-re, hanem Contact-ra mutatnak. Itt a Contact-on keresztül jutunk el
    a hozzá tartozó Client-hez."""
    contact_id = resolve_relation_id(db, "Contact", notion_contact_page_ids)
    if contact_id is None:
        return None
    contact = db.get(Contact, contact_id)
    return contact.client_id if contact else None


def get_or_create_unknown_client(db: Session) -> Client:
    """Ha egy Project Code-hoz nem oldható fel a Notion 'Megrendelői kontaktok' relation
    (pl. mert az adott kontakt lap üres volt), ide kötjük, hogy ne vesszen el az adat."""
    from sqlalchemy import select

    from app.models.notion_import import NotionImportMap

    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == UNKNOWN_CLIENT_KEY))
    if mapping:
        return db.get(Client, mapping.entity_id)
    client, _ = upsert(db, Client, "Client", UNKNOWN_CLIENT_KEY, {"nev": "Ismeretlen ügyfél (Notion import)"})
    return client


_CONTACT_CONSUMED = {
    "Vállalkozás neve",
    "Full Name",
    "Adószám",
    "Székhely",
    "Nyilvántartásiszám",
    "Képviselő",
    "Email",
    "Phone",
}


def import_clients_and_contacts(client: NotionClient, db: Session) -> ImportResult:
    """Client + Contact <- 'Megrendelői kontaktok'. A Notion tábla kontakt-szinten
    tárolja a cégadatokat is, ezért (Vállalkozás neve, Adószám) alapján csoportosítva
    hozzuk létre a Client rekordokat, és minden Notion page egy Contact lesz. A fel nem
    használt mezők (pl. reverse-relationök más táblákra) a Contact.extra-ba kerülnek -
    a Client szintetikus, több kontakthoz tartozó kulcs, nincs saját "extra"-ja."""
    result = ImportResult(entity_type="Client+Contact")
    company_key_to_client: dict[str, Client] = {}

    for page in client.query_database(db_ids.MEGRENDELOI_KONTAKTOK):
        props = extract_properties(page)
        company_name = _text(props.get("Vállalkozás neve")) or _text(props.get("Full Name"))
        if not company_name:
            result.skipped += 1
            continue

        adoszam = _text(props.get("Adószám"))
        company_key = f"client:{adoszam or company_name.lower()}"

        hype_client = company_key_to_client.get(company_key)
        if hype_client is None:
            hype_client = safe_upsert(
                db,
                result,
                Client,
                "Client",
                company_key,
                {
                    "nev": company_name,
                    "adoszam": adoszam,
                    "szekhely": _text(props.get("Székhely")),
                    "nyilvantartasi_szam": _text(props.get("Nyilvántartásiszám")),
                    "kepviselo": _text(props.get("Képviselő")),
                },
                label=f"Client '{company_name}'",
            )
            if hype_client is None:
                continue
            company_key_to_client[company_key] = hype_client

        full_name = _text(props.get("Full Name"))
        if not full_name:
            continue
        safe_upsert(
            db,
            result,
            Contact,
            "Contact",
            page["id"],
            {
                "client_id": hype_client.id,
                "full_name": full_name,
                "email": _text(props.get("Email")),
                "phone": _text(props.get("Phone")),
                "extra": remaining_properties(props, _CONTACT_CONSUMED),
            },
            label=f"Contact '{full_name}'",
        )

    return result


_EMPLOYEE_CONSUMED = {
    "Full Name",
    "E-MAIL CÍM",
    "Email",
    "TELEFONSZÁM",
    "Phone",
    "JOGOSÍTVÁNY",
    "Munkaszerződés",
    "Külsős vagy belsős",
}


def import_employees(client: NotionClient, db: Session) -> ImportResult:
    """Employee <- 'Külsős és belsős' (a valódi crew-directory tábla; a doksi által
    feltételezett további forrásokból - Belsős, Külsős - a discovery alapján kiderült,
    hogy azok inkább TIG/számla-nyilvántartó táblák, nem employee-directory, ezért
    ezekből NEM hozunk létre külön Employee rekordokat)."""
    result = ImportResult(entity_type="Employee")

    for page in client.query_database(db_ids.KULSOS_ES_BELSOS):
        props = extract_properties(page)
        full_name = _text(props.get("Full Name"))
        if not full_name:
            result.skipped += 1
            continue

        tipus_raw = props.get("Külsős vagy belsős") or []
        tipus = EmployeeType.KULSOS
        joined = " ".join(tipus_raw).lower() if isinstance(tipus_raw, list) else str(tipus_raw).lower()
        if "bels" in joined:
            tipus = EmployeeType.BELSOS

        safe_upsert(
            db,
            result,
            Employee,
            "Employee",
            page["id"],
            {
                "full_name": full_name,
                "tipus": tipus,
                "email": _text(props.get("E-MAIL CÍM")) or _text(props.get("Email")),
                "telefon": _text(props.get("TELEFONSZÁM")) or _text(props.get("Phone")),
                "jogositvany": _text(props.get("JOGOSÍTVÁNY")),
                "munkaszerzodes_url": _first_url(props.get("Munkaszerződés")),
                "role": SystemRole.OPERATOR,
                "is_active": True,
                "extra": remaining_properties(props, _EMPLOYEE_CONSUMED),
            },
            label=f"Employee '{full_name}'",
        )

    # Type-overlay: a Vágók tábla '👥 Külsős és belsős' relation-je jelöli ki, ki vágó -
    # ez valódi relation (nem név-egyeztetés), tehát biztonságosan használható.
    for page in client.query_database(db_ids.VAGOK):
        props = extract_properties(page)
        related_ids = props.get("👥 Külsős és belsős") or []
        employee_id = resolve_relation_id(db, "Employee", related_ids)
        if employee_id is None:
            result.skipped += 1
            continue
        try:
            with db.begin_nested():
                employee = db.get(Employee, employee_id)
                employee.tipus = EmployeeType.VAGO
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Vágó type-overlay (employee_id={employee_id}): {type(exc).__name__}: {exc}")

    return result


def import_rates(client: NotionClient, db: Session) -> ImportResult:
    """Rate <- 'Órabér/napibér', a 'Személy' relation alapján kötve az Employee-hez."""
    result = ImportResult(entity_type="Rate")

    for page in client.query_database(db_ids.ORABER_NAPIBER):
        props = extract_properties(page)
        employee_id = resolve_relation_id(db, "Employee", props.get("Személy") or [])
        if employee_id is None:
            result.skipped += 1
            continue

        safe_upsert(
            db,
            result,
            Rate,
            "Rate",
            page["id"],
            {
                "employee_id": employee_id,
                "orabler": props.get("Órabér"),
                "napibler": props.get("Napibér"),
                "tulora": props.get("Túlóra"),
                "plusz_nap": props.get("Plusz nap"),
                "havi_alap": props.get("Havi alap"),
                "elso_munkanap": as_date(props.get("Első munkanap")),
                "utolso_munkanap": as_date(props.get("Utolsó munkanap")),
            },
            label=f"Rate (employee_id={employee_id})",
        )

    return result


def _normalize_track_mode(raw: str | None) -> TrackMode:
    if raw and any(kw in raw.lower() for kw in ("stock", "készlet", "darab")):
        return TrackMode.STOCK
    return TrackMode.ASSET


_EQUIPMENT_CONSUMED = {
    "Name",
    "Serial number",
    "Kategória",
    "Állapota",
    "Archive státusz",
    "Track mode",
    "Összes mennyiség",
}


def import_equipment(client: NotionClient, db: Session) -> ImportResult:
    """Equipment <- 'Leltár'."""
    result = ImportResult(entity_type="Equipment")

    for page in client.query_database(db_ids.LELTAR):
        props = extract_properties(page)
        nev = _text(props.get("Name"))
        if not nev:
            result.skipped += 1
            continue

        osszes_mennyiseg = props.get("Összes mennyiség")
        safe_upsert(
            db,
            result,
            Equipment,
            "Equipment",
            page["id"],
            {
                "nev": nev,
                "serial_number": _text(props.get("Serial number")),
                "kategoria": _text(props.get("Kategória")),
                "allapot": _text(props.get("Állapota")),
                "archive_statusz": _text(props.get("Archive státusz")),
                "track_mode": _normalize_track_mode(props.get("Track mode")),
                "osszes_mennyiseg": int(osszes_mennyiseg) if osszes_mennyiseg else None,
                "extra": remaining_properties(props, _EQUIPMENT_CONSUMED),
            },
            label=f"Equipment '{nev}'",
        )

    return result


_CAMPAIGN_CONSUMED = {"Kampány neve", "Kampány státusza", "Határidő", "Intervalluma", "Kész"}


def import_campaigns(client: NotionClient, db: Session) -> ImportResult:
    """Campaign <- 'Kampányok'."""
    result = ImportResult(entity_type="Campaign")

    for page in client.query_database(db_ids.KAMPANYOK):
        props = extract_properties(page)
        nev = _text(props.get("Kampány neve"))
        if not nev:
            result.skipped += 1
            continue

        intervalluma = props.get("Intervalluma")
        intervalluma_text = intervalluma.get("start") if isinstance(intervalluma, dict) else None

        safe_upsert(
            db,
            result,
            Campaign,
            "Campaign",
            page["id"],
            {
                "nev": nev,
                "kampany_statusza": _text(props.get("Kampány státusza")),
                "hatarido": as_date(props.get("Határidő")),
                "intervalluma": intervalluma_text,
                "kesz": bool(props.get("Kész")),
                "extra": remaining_properties(props, _CAMPAIGN_CONSUMED),
            },
            label=f"Campaign '{nev}'",
        )

    return result


_TASK_CONSUMED = {
    "Feladat",
    "Name",
    "Állapot",
    "Status",
    "Határidő",
    "Date",
    "Due date",
    "Kategória",
    "Checked",
    "Leírás",
}


def _import_task_database(
    client: NotionClient, db: Session, database_id: str, result: ImportResult, forced_allapot: str | None = None
) -> None:
    for page in client.query_database(database_id):
        props = extract_properties(page)
        feladat = _text(props.get("Feladat")) or _text(props.get("Name"))
        if not feladat:
            result.skipped += 1
            continue

        safe_upsert(
            db,
            result,
            Task,
            "Task",
            page["id"],
            {
                "feladat": feladat,
                "allapot": forced_allapot or _text(props.get("Állapot")) or _text(props.get("Status")),
                "hatarido": as_date(props.get("Határidő")) or as_date(props.get("Date")) or as_date(props.get("Due date")),
                "kategoria": _text(props.get("Kategória")),
                "checked": bool(props.get("Checked", False)),
                "leiras": _text(props.get("Leírás")),
                "extra": remaining_properties(props, _TASK_CONSUMED),
            },
            label=f"Task '{feladat}'",
        )


def import_tasks(client: NotionClient, db: Session) -> ImportResult:
    """Task <- TEENDŐK + Ági to do list + HYPE TO-DO LIST + Archive feladatok (status=archived)."""
    result = ImportResult(entity_type="Task")
    _import_task_database(client, db, db_ids.TEENDOK, result)
    _import_task_database(client, db, db_ids.AGI_TODO_LIST, result)
    _import_task_database(client, db, db_ids.HYPE_TODO_LIST, result)
    _import_task_database(client, db, db_ids.ARCHIVE_FELADATOK, result, forced_allapot="archived")
    return result


_KERETSZERZODES_CONSUMED = {
    "Akivel szerződünk",
    "Szerződés",
    "Cég neve",
    "Székhely",
    "Adószám",
    "Megbízás tárgya",
    "Keretszerződés állapota",
    "Keltezés",
}
_ALVALLALKOZOI_CONSUMED = {
    "Vállalkozó",
    "Szerződés aláírva",
    "Vállalkozás neve",
    "Vállalkozás székhelye",
    "Vállalkozás adószáma",
    "Megbízás tárgya",
    "Állapot",
    "Keltezés dátuma",
}


def import_contracts(client: NotionClient, db: Session) -> ImportResult:
    """Contract <- 'Keretszerződés' (tipus=kereto) + 'Alvállakozó keretszerződés (külsős)' (tipus=alvallalkozoi)."""
    result = ImportResult(entity_type="Contract")

    for page in client.query_database(db_ids.KERETSZERZODES):
        props = extract_properties(page)
        client_id = resolve_client_via_contact(db, props.get("Akivel szerződünk") or [])
        szerzodes_url = _first_url(props.get("Szerződés"))
        safe_upsert(
            db,
            result,
            Contract,
            "Contract",
            page["id"],
            {
                "tipus": ContractType.KERETSZERZODES,
                "client_id": client_id,
                "ceg_neve": _text(props.get("Cég neve")),
                "szekhely": _text(props.get("Székhely")),
                "adoszam": _text(props.get("Adószám")),
                "megbizas_targya": _text(props.get("Megbízás tárgya")),
                "szerzodes_allapota": _text(props.get("Keretszerződés állapota")),
                "szerzodes_file_url": szerzodes_url,
                "keltezes": as_date(props.get("Keltezés")),
                "alairva": bool(szerzodes_url),
                "extra": remaining_properties(props, _KERETSZERZODES_CONSUMED),
            },
            label="Contract (keretszerződés)",
        )

    for page in client.query_database(db_ids.ALVALLALKOZO_KERETSZERZODES):
        props = extract_properties(page)
        employee_id = resolve_relation_id(db, "Employee", props.get("Vállalkozó") or [])
        szerzodes_url = _first_url(props.get("Szerződés aláírva"))
        safe_upsert(
            db,
            result,
            Contract,
            "Contract",
            page["id"],
            {
                "tipus": ContractType.ALVALLALKOZOI,
                "employee_id": employee_id,
                "ceg_neve": _text(props.get("Vállalkozás neve")),
                "szekhely": _text(props.get("Vállalkozás székhelye")),
                "adoszam": _text(props.get("Vállalkozás adószáma")),
                "megbizas_targya": _text(props.get("Megbízás tárgya")),
                "szerzodes_allapota": _text(props.get("Állapot")),
                "szerzodes_file_url": szerzodes_url,
                "keltezes": as_date(props.get("Keltezés dátuma")),
                "alairva": bool(szerzodes_url),
                "extra": remaining_properties(props, _ALVALLALKOZOI_CONSUMED),
            },
            label="Contract (alvállalkozói keretszerződés)",
        )

    return result


_PROJECT_CODE_CONSUMED = {
    "PROJEKTKÓD",
    "Megrendelői kontaktok",
    "Dátum",
    "Esemény állapota",
    "Pénznem",
    "Árfolyam",
    "TIG státusza",
    "Számla státusza",
    "Keretszerződés",
    "MEGJEGYZÉS",
    "Teljesítés dátuma",
    "Utalás dátuma",
    "Számla",
    "TIG aláírva",
}


def import_project_codes(client: NotionClient, db: Session) -> ImportResult:
    """ProjectCode <- 'HYPE ADMIN projektkódok'. Ha a 'Megrendelői kontaktok' relation
    nem oldható fel (pl. üres kontakt-lap volt), az 'Ismeretlen ügyfél' placeholder
    Client-hez kötjük, hogy a pénzügyi adat ne vesszen el. A tábla 60+ mezős - a
    kevésbé fontos, nagyrészt Notion-formulából számolt mezők az `extra` JSON-ba
    kerülnek (lásd remaining_properties), nem kapnak saját oszlopot."""
    result = ImportResult(entity_type="ProjectCode")
    unknown_client = get_or_create_unknown_client(db)

    for page in client.query_database(db_ids.HYPE_ADMIN_PROJEKTKODOK):
        props = extract_properties(page)
        projektkod = _text(props.get("PROJEKTKÓD"))
        if not projektkod:
            result.skipped += 1
            continue

        client_id = resolve_client_via_contact(db, props.get("Megrendelői kontaktok") or []) or unknown_client.id
        contract_id = resolve_relation_id(db, "Contract", props.get("Keretszerződés") or [])

        safe_upsert(
            db,
            result,
            ProjectCode,
            "ProjectCode",
            page["id"],
            {
                "projektkod": projektkod,
                "client_id": client_id,
                "contract_id": contract_id,
                "datum": as_date(props.get("Dátum")),
                "esemeny_allapota": _text(props.get("Esemény állapota")),
                "penznem": _text(props.get("Pénznem")) or "HUF",
                "arfolyam": props.get("Árfolyam"),
                "tig_statusza": _text(props.get("TIG státusza")),
                "szamla_statusza": _text(props.get("Számla státusza")),
                "megjegyzes": _text(props.get("MEGJEGYZÉS")),
                "teljesites_datuma": as_date(props.get("Teljesítés dátuma")),
                "utalas_datuma": as_date(props.get("Utalás dátuma")),
                "szamla_url": _first_url(props.get("Számla")),
                "tig_alairva_url": _first_url(props.get("TIG aláírva")),
                "extra": remaining_properties(props, _PROJECT_CODE_CONSUMED),
            },
            label=f"ProjectCode '{projektkod}'",
        )

    return result
