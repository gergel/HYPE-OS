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
from app.notion_import.client import NotionClient, as_date, as_datetime, extract_properties
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


def import_clients_and_contacts(client: NotionClient, db: Session) -> ImportResult:
    """Client + Contact <- 'Megrendelői kontaktok'. A Notion tábla kontakt-szinten
    tárolja a cégadatokat is, ezért (Vállalkozás neve, Adószám) alapján csoportosítva
    hozzuk létre a Client rekordokat, és minden Notion page egy Contact lesz. A fel nem
    használt mezők (pl. reverse-relationök más táblákra) a Contact.extra-ba kerülnek -
    a Client szintetikus, több kontakthoz tartozó kulcs, nincs saját "extra"-ja."""
    result = ImportResult(entity_type="Client+Contact")
    company_key_to_client: dict[str, Client] = {}

    for page in client.query_database(db_ids.MEGRENDELOI_KONTAKTOK):
        props = extract_properties(page, client)
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
                "keresztnev_notion": _text(props.get("Keresztnév")),
                "vezeteknev_notion": _text(props.get("Vezeték név")),
                "torolt_anyagok_notion_ids": props.get("Törölt anyagok"),
                "kreativ_team_database_notion_ids": props.get("Kreatív team database"),
            },
            label=f"Contact '{full_name}'",
        )

    return result




def import_employees(client: NotionClient, db: Session) -> ImportResult:
    """Employee <- 'Külsős és belsős' (a valódi crew-directory tábla; a doksi által
    feltételezett további forrásokból - Belsős, Külsős - a discovery alapján kiderült,
    hogy azok inkább TIG/számla-nyilvántartó táblák, nem employee-directory, ezért
    ezekből NEM hozunk létre külön Employee rekordokat)."""
    result = ImportResult(entity_type="Employee")

    for page in client.query_database(db_ids.KULSOS_ES_BELSOS):
        props = extract_properties(page, client)
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
                "role": SystemRole.OPERATOR,
                "is_active": True,
                "elso_munkanap": as_date(props.get("Első munkanap")),
                "utolso_munkanap": as_date(props.get("Utolsó munkanap")),
                "ertekeles": props.get("Értékelés"),
                "technikai_ismeret": _text(props.get("TECHNIKAI ISMERET")),
                "vallalkozas_kepviselo": _text(props.get("Vállalkozás képviselő")),
                "leltar_notion_ids": props.get("🎥 Leltár"),
                "hany_visszajelzese_van_notion": props.get("Hány visszajelzése van"),
                "first_name": _text(props.get("First name")),
                "last_name": _text(props.get("Last name")),
                "munkanapok_notion": props.get("Munkanapok"),
                "linkedin_profile": props.get("LinkedIn Profile"),
                "twitter_profile": props.get("Twitter Profile"),
                "facebook_profile": props.get("Facebook Profile"),
                "photo_url": _first_url(props.get("Photo")),
                "kulsos_tig_notion_ids": props.get("Külsős TIG"),
                "belsos_tig_notion_ids": props.get("Belsős TIG"),
                "orabler_notion": _text(props.get("Órabér")),
                "napidij_notion": _text(props.get("Napidíj")),
                "extra_kiadas_megnevezes": _text(props.get("Extra kiadás megnevezés")),
                "extra_kiadas_osszeg": props.get("Extra kiadás összeg"),
                "extra_kiadas_datuma": as_date(props.get("Extra kiadás dátuma")),
                "belsos_havi_tig": props.get("Belsős Havi TIG"),
                "source": _text(props.get("Source")),
                "events_involved_count_notion": props.get("Events involved count (Σ)"),
                "netto_osszeg": props.get("Nettó összeg"),
                "linked_events_notion_ids": props.get("Linked Events"),
                "leltar_hiany_20240415_notion": props.get("2024.04.15. leltár hiány"),
                "legutolso_napi_dij_megegyezes": _text(props.get("LEGUTOLSÓ NAPI DÍJ MEGEGYEZÉS")),
                "milyen_suru_hivjuk": _text(props.get("MILYEN SŰRŰN HÍVJUK")),
                "megbizas_targya": _text(props.get("Megbízás tárgya")),
                "szallito_notion_ids": props.get("Szállító"),
                "keltezes_datuma": as_date(props.get("Keltezés dátuma")),
                "archive_technika_elhagyas_notion_ids": props.get("Archive technika elhagyás"),
                "nyilvantartasi_szam": _text(props.get("Nyilvántartási szám:")),
                "vallakozas_szekhely": _text(props.get("Vállakozás székhely")),
                "van_e_email_cime_notion": props.get("van e email címe"),
                "vallakozas_neve": _text(props.get("Vállakozás neve")),
                "phone_2": props.get("Phone 2"),
                "megjegyzes": _text(props.get("MEGJEGYZÉS")),
                "honnan_ismerjuk": _text(props.get("HONNAN ISMERJÜK")),
                "birthday": as_date(props.get("Birthday")),
                "kiadas_projektkodja_notion_ids": props.get("Kiadás projektkódja"),
                "formula_2_notion": props.get("Formula 2"),
                "main_database_notion_ids": props.get("📅 Main Database"),
                "vallalkozas_adoszama": _text(props.get("Vállalkozás adószáma")),
                "plusz_afa": _text(props.get("Plusz ÁFA")),
            },
            label=f"Employee '{full_name}'",
        )

    # Szerepkör-overlay: a Vágók tábla '👥 Külsős és belsős' relation-je jelöli
    # ki, ki vágó - ez valódi relation (nem név-egyeztetés), tehát biztonságosan
    # használható. A ROLE-t állítjuk, NEM a tipus-t: a tipus azt mondja meg,
    # hogy valaki külsős vagy belsős (ezt épp a forrás-tábla neve is jelzi),
    # és korábban ezt írta felül az overlay - vagyis pont azt az információt
    # törölte, amiért a relation létezik.
    for page in client.query_database(db_ids.VAGOK):
        props = extract_properties(page, client)
        related_ids = props.get("👥 Külsős és belsős") or []
        employee_id = resolve_relation_id(db, "Employee", related_ids)
        if employee_id is None:
            result.skipped += 1
            continue
        try:
            with db.begin_nested():
                employee = db.get(Employee, employee_id)
                # Admint/operátort nem fokozunk le: náluk a vágó-szerep
                # kevesebb jogot jelentene, mint amijük van.
                if employee.role not in (SystemRole.ADMIN, SystemRole.OPERATOR):
                    employee.role = SystemRole.VAGO
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Vágó type-overlay (employee_id={employee_id}): {type(exc).__name__}: {exc}")

    return result


def import_rates(client: NotionClient, db: Session) -> ImportResult:
    """Rate <- 'Órabér/napibér', a 'Személy' relation alapján kötve az Employee-hez."""
    result = ImportResult(entity_type="Rate")

    for page in client.query_database(db_ids.ORABER_NAPIBER):
        props = extract_properties(page, client)
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
                "fotos_napi_ber": props.get("Fotós napi bér"),
                "nev": _text(props.get("Name")),
            },
            label=f"Rate (employee_id={employee_id})",
        )

    return result


def _normalize_track_mode(raw: str | None) -> TrackMode:
    if raw and any(kw in raw.lower() for kw in ("stock", "készlet", "darab")):
        return TrackMode.STOCK
    return TrackMode.ASSET


def import_equipment(client: NotionClient, db: Session) -> ImportResult:
    """Equipment <- 'Leltár'."""
    result = ImportResult(entity_type="Equipment")

    for page in client.query_database(db_ids.LELTAR):
        props = extract_properties(page, client)
        nev = _text(props.get("Name"))
        if not nev:
            result.skipped += 1
            continue

        osszes_mennyiseg = props.get("Összes mennyiség")
        hany_napot_dolgozott = props.get("Hány napot dolgozott")
        stock_qty = props.get("Stock qty")
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
                "leltar_20240415": props.get("2024.04.15. Leltár"),
                "leltar_20250104": props.get("2025.01.04. Leltár"),
                "hasznalhato": _text(props.get("Használható?")),
                "leltar_20240526": props.get("2024.05.26. Leltár"),
                "rendszerbe_kerules_idopontja": as_datetime(props.get("Rendszerbe kerülés időpontja")),
                "letrehozta_notion": props.get("Created by"),
                "leltar_20240620": props.get("2024.06.20. Leltár"),
                "hany_napot_dolgozott": hany_napot_dolgozott if isinstance(hany_napot_dolgozott, (int, float)) else None,
                "status_notion": _text(props.get("status")),
                "hany_forgatason_vett_reszt": _text(props.get("Hány forgatáson vett részt")),
                "mai_notion": props.get("mai"),
                "leltar_20250519": props.get("2025.05.19. - Leltár"),
                "qr_kod": _text(props.get("QR kód")),
                "created_at_notion": as_datetime(props.get("Created time")),
                "leltar_tetelek_notion_ids": props.get("Leltár tételek"),
                "forgatasi_napok": _text(props.get("Forgatási napok")),
                "projektek_notion_ids": props.get("Projektek"),
                "qr": _text(props.get("QR")),
                "eszkozkiviteli_ki_notion_ids": props.get("eszközkiviteli ki"),
                "eszkozkiviteli_vissza_notion_ids": props.get("eszközkiviteli vissza"),
                "megjegyzes": _text(props.get("Megjegyzés")),
                "stock_qty": stock_qty if isinstance(stock_qty, (int, float)) else None,
                "zoom_atfogas": props.get("Zoom átfogás"),
                "stock_igenyek_notion_ids": props.get("Stock igények"),
                "jovobeni": _text(props.get("JÖVŐBENI")),
                "megeri_e_szerelni": _text(props.get("Megéri e szerelni")),
                "szerviz_leiras": _text(props.get("Szervíz leírás")),
                "selejtezes_elhagyas_datuma": as_date(props.get("Selejtezés /elhagyás dátuma")),
                "ahol_utoljara_volt": _text(props.get("Ahol utoljára volt")),
            },
            label=f"Equipment '{nev}'",
        )

    return result


def import_campaigns(client: NotionClient, db: Session) -> ImportResult:
    """Campaign <- 'Kampányok'."""
    result = ImportResult(entity_type="Campaign")

    for page in client.query_database(db_ids.KAMPANYOK):
        props = extract_properties(page, client)
        nev = _text(props.get("Kampány neve"))
        if not nev:
            result.skipped += 1
            continue

        intervalluma = props.get("Intervalluma")
        intervalluma_text = intervalluma.get("start") if isinstance(intervalluma, dict) else None
        felelos_employee_id = resolve_relation_id(db, "Employee", props.get("Kampány felelőse") or [])

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
                "felelos_employee_id": felelos_employee_id,
                "forgatas_utomunka": _text(props.get("Forgatás/utómunka")),
                "forgatas": props.get("Forgatás?"),
                "kreativ_team_database_notion_ids": props.get("Kreatív team database"),
                "van_utomunka": props.get("Utómunka?"),
                "kampany_felelose_notion_ids": props.get("Kampány felelőse"),
                "leiras": _text(props.get("Leírás")),
                "utomunka_szoveg": _text(props.get("Utómunka")),
                "forgatasok_notion_ids": props.get("Forgatások"),
            },
            label=f"Campaign '{nev}'",
        )

    return result


def _import_task_database(
    client: NotionClient, db: Session, database_id: str, result: ImportResult, forced_allapot: str | None = None
) -> None:
    for page in client.query_database(database_id):
        props = extract_properties(page, client)
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
                "aki_felvezette_notion": props.get("Aki felvezette"),
                "letrehozas_idopontja": as_datetime(props.get("Létrehozás időpontja")),
                "felelos_notion": props.get("Felelős"),
                "ugyfel": _text(props.get("Ügyfél")),
                "ellenorzes_felelos_notion": props.get("Ellenőrzés felelős"),
                "aki_ellenorizte_keszbe_rakta_notion": props.get("Aki ellenőrizte/készbe rakta"),
                "kovetkezo_lepes": _text(props.get("Következő lépés")),
                "csatolni_valo_urls": props.get("Csatolni való"),
                "files_media_urls": props.get("Files & media"),
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


def import_contracts(client: NotionClient, db: Session) -> ImportResult:
    """Contract <- 'Keretszerződés' (tipus=kereto) + 'Alvállakozó keretszerződés (külsős)' (tipus=alvallalkozoi)."""
    result = ImportResult(entity_type="Contract")

    for page in client.query_database(db_ids.KERETSZERZODES):
        props = extract_properties(page, client)
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
                "letrehozta_notion": props.get("Created by"),
                "vallalkozas_kepviseloje": _text(props.get("Vállalkozás képviselője")),
                "created_at_notion": as_datetime(props.get("Created time")),
                "keretszerzodes_kuld": props.get("Keretszerződés küld"),
                "email": _text(props.get("Email")),
                "szemely_notion_ids": props.get("Személy"),
                "nev": _text(props.get("Name")),
                "kulsos_notion_ids": props.get("Külsős "),
                "vallalkozas_nyilvantartasi_szam": _text(props.get("Vállalkozás nyilvántartási szám")),
                "szerzodes_megjegyzes": _text(props.get("Szerződés megjegyzés")),
            },
            label="Contract (keretszerződés)",
        )

    for page in client.query_database(db_ids.ALVALLALKOZO_KERETSZERZODES):
        props = extract_properties(page, client)
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
                "letrehozta_notion": props.get("Created by"),
                "vallalkozas_kepviseloje": _text(props.get("Vállalkozás képviselője")),
                "created_at_notion": as_datetime(props.get("Created time")),
                "keretszerzodes_kuld": props.get("Keretszerződés küld"),
                "email": _text(props.get("Email")),
                "szemely_notion_ids": props.get("Személy"),
                "nev": _text(props.get("Name")),
                "kulsos_notion_ids": props.get("Külsős "),
                "vallalkozas_nyilvantartasi_szam": _text(props.get("Vállalkozás nyilvántartási szám")),
                "szerzodes_megjegyzes": _text(props.get("Szerződés megjegyzés")),
            },
            label="Contract (alvállalkozói keretszerződés)",
        )

    return result


def import_project_codes(client: NotionClient, db: Session) -> ImportResult:
    """ProjectCode <- 'HYPE ADMIN projektkódok'. Ha a 'Megrendelői kontaktok' relation
    nem oldható fel (pl. üres kontakt-lap volt), az 'Ismeretlen ügyfél' placeholder
    Client-hez kötjük, hogy a pénzügyi adat ne vesszen el. A tábla 81 mezős - a
    felhasználó döntése alapján (2026-07-02) minden mező saját oszlopot kap (lásd
    app/models/project_code.py), nincs közös 'extra' JSON gyűjtőmező. Az 'Utómunka'/
    'Bevételek'/'Forgatások'/'Projekt kiadások'/'Belsős extra kiadások' Notion
    relationöket szándékosan nem vesszük át külön mezőként, mert ugyanazt az adatot
    duplikálnák, amit a Deliverable/Revenue/Project/Expense.project_code_id már
    helyesen, fordított irányból hordoz."""
    result = ImportResult(entity_type="ProjectCode")
    unknown_client = get_or_create_unknown_client(db)

    for page in client.query_database(db_ids.HYPE_ADMIN_PROJEKTKODOK):
        props = extract_properties(page, client)
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
                "teljesites_datum_formazva": _text(props.get("Teljesítés dátum formáz")),
                "netto_osszeg": props.get("Nettó összeg"),
                "megrendelo_szekhelye": _text(props.get("Megrendelő  székhelye")),
                "profit_szazalek_notion": props.get("Profit százalék"),
                "geri_projekt": _text(props.get("Geri projekt")),
                "szerzodes_targya": _text(props.get("Szerződés tárgya")),
                "keltezes_datum_formazva": _text(props.get("Keltezés dátum formáz")),
                "gyartasi_koltseg_notion": props.get("Gyártási költség"),
                "szerzodes_specialis_eset": _text(props.get("Szerződés speciális eset")),
                "fizetesi_hatarido": as_date(props.get("Fizetési határidő")),
                "megrendelo_nyilvantartasi_szam": _text(props.get("Megrendelő nyilvántartásiszám")),
                "szerzodes_kuldes": bool(props.get("Szerződés küldés")),
                "osszes_koltseg_notion": props.get("Összes költség"),
                "tig_teljesitesi_ido": _text(props.get("TIG teljesítési idő")),
                "megrendelo_neve": _text(props.get("Megrendelő neve")),
                "osszesen_netto_notion": props.get("Összesen nettó"),
                "megrendelo_adoszama": _text(props.get("Megrendelő adószáma")),
                "netto_notion": props.get("Nettó"),
                "helyszin": _text(props.get("HELYSZÍN")),
                "datum_megjegyzes": _text(props.get("DÁTUM megjegyzés")),
                "szerzodes_plusz_afa": _text(props.get("Szerződés plus ÁFA")),
                "tig_projektnev": _text(props.get("TIG projektnév")),
                "specialis_eset": _text(props.get("Speciális eset")),
                "szerzodes_helye": _text(props.get("Szerződés helye")),
                "szerzodes_netto_osszeg": props.get("Szerződés nettó összeg"),
                "megrendeloi_emailek": _text(props.get("megrendelői emailek")),
                "brutto_notion": props.get("Bruttó"),
                "kulsos_notion_ids": props.get("Külsős"),
                "alvallalkozok_koltsege_notion": props.get("Alvállalkozók költsége"),
                "darabolva": props.get("Darabolva"),
                "vagasi_koltseg_notion": props.get("Vágási költség"),
                "project_nev": _text(props.get("PROJECT NÉV")),
                "szerzodes_statusza": _text(props.get("Szerződés státusza")),
                "plusz_afa": _text(props.get("Plusz ÁFA")),
                "megerte_e": props.get("Megérte-e"),
                "megrendelo_kepviseloje": _text(props.get("Megrendelő képviselője")),
                "szerzodes_projekt_nev": _text(props.get("Szerződés projekt név")),
                "teljesites": _text(props.get("Teljesítés")),
                "tig_kikuldve": bool(props.get("TIG kiküldve")),
                "adminisztracios_tablaban": _text(props.get("ADMINISZTRÁCIÓS TÁBLÁBAN?")),
                "tig_specialis": _text(props.get("TIG Speciális")),
                "keltezes_datuma": as_date(props.get("Keltezés dátuma")),
                "lejart_notion": props.get("Lejárt"),
                "megbizas_targya": _text(props.get("Megbízás tárgya")),
                "belsos_koltseg_akkor": props.get("Belsős költség akkor"),
                "vallalasi_ar_notion": props.get("Vállalási ár"),
                "tovabbi_dokumentumok": props.get("További dokumentumok"),
                "utomunkak_notion": props.get("Utómunkák"),
                "bevetel_formaja": _text(props.get("Bevétel formája")),
                "darabolas_notion_ids": props.get("HYPE ADMIN PROJEKTKÓDOK DARABOLÁS"),
                "megrendelo_email": _text(props.get("Megrendelő email")),
                "forintban_notion": props.get("Forintban"),
                "szerzodes_keltezes_datuma": as_date(props.get("Szerződés keltezés dátuma")),
                "belsos_koltseg_notion": props.get("Belsős költség"),
                "belso_plusz_koltseg_notion": props.get("Belső plusz költség"),
                "tig_url": props.get("TIG url"),
            },
            label=f"ProjectCode '{projektkod}'",
        )

    return result
