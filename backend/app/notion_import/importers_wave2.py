"""2. kör importerek: a Main Database-re (Project) és az arra épülő láncra
(Deliverable, Timesheet, Finance, Feedback) épülő entitások. Csak az 1. kör
(importers.py) sikeres lefutása után van értelme futtatni, mert ezek Client/
Employee/Campaign/ProjectCode relation-öket oldanak fel.

A felhasználó explicit döntése alapján (2026-07-02) az alábbi táblát NEM
importáljuk, mert csak teszt volt, nincs rá szükség:
- Callsheet <- 'Operatőri diszpó'

Az Assignment (eszköz-foglalás egy projekthez) két forrásból töltődik: a
'Leltár' relation-ből (itt, lásd _link_leltar_equipment - egyedi "asset"
eszközök, qty=1) és a 'Stock igények' Notion adatbázisból (lásd
importers_wave3.import_stock_igenyek - darabszámos "stock" eszközök) - a
felhasználó kérése szerint ez a két korábban külön kezelt mechanizmus egyetlen
Assignment-alapú foglalási modellben egyesül."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.equipment import Assignment
from app.models.feedback import Feedback
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.timesheet import Timesheet
from app.notion_import import database_ids as db_ids
from app.notion_import.client import NotionClient, as_date, as_datetime, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, resolve_relation_ids, safe_upsert, upsert
from app.notion_import.importers import _text, get_or_create_unknown_client

UNKNOWN_PROJECT_CODE_KEY = "project_code:unknown-notion-import"


def _split_date_range(value: str | None) -> tuple:
    """A extract_property() már lelapított "kezdő – záró" alakú range-stringet
    (vagy sima "kezdő" dátumot) bontja szét (kezdő, záró) date-ekre - a Technika
    ready ütközés-ellenőrzéshez kell a projekt teljes forgatási naptartománya,
    nem csak a kezdő nap."""
    if not value:
        return None, None
    if isinstance(value, str) and " – " in value:
        start_s, end_s = value.split(" – ", 1)
        return as_date(start_s), as_date(end_s)
    return as_date(value), None


def _link_leltar_equipment(db: Session, project: Project, props: dict) -> None:
    """A 'Leltár' relation (a Main oldalon kereséssel/kattintással hozzáadható
    eszközök) feloldása Assignment sorokká - qty=1, mert ez a relation nem hordoz
    darabszámot (a darabszámos eszközöket a 'Stock igények' táblából oldjuk fel,
    lásd importers_wave3.import_stock_igenyek). Nem duplikál újrafuttatáskor."""
    equipment_notion_ids = props.get("Leltár") or []
    if not equipment_notion_ids:
        return
    equipment_ids = resolve_relation_ids(db, "Equipment", equipment_notion_ids)
    if not equipment_ids:
        return
    already_linked = {
        a.equipment_id
        for a in db.scalars(select(Assignment).where(Assignment.project_id == project.id))
    }
    for equipment_id in equipment_ids:
        if equipment_id in already_linked:
            continue
        db.add(Assignment(project_id=project.id, equipment_id=equipment_id, qty=1))
    db.flush()


def _link_attendees_crew(db: Session, project: Project, props: dict) -> None:
    """Az 'Attendees Contacts' relation (kétirányú kapcsolat a 'Külsős és belsős'
    (Employee) adatbázissal - itt lehet névvel embereket hozzáadni egy projekthez)
    feloldása a project.crew m2m kapcsolattá."""
    people_notion_ids = props.get("Attendees Contacts") or []
    if not people_notion_ids:
        return
    employee_ids = resolve_relation_ids(db, "Employee", people_notion_ids)
    if not employee_ids:
        return
    current_ids = {e.id for e in project.crew}
    new_ids = [eid for eid in employee_ids if eid not in current_ids]
    if not new_ids:
        return
    new_employees = db.scalars(select(Employee).where(Employee.id.in_(new_ids))).all()
    project.crew = list(project.crew) + list(new_employees)
    db.flush()


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
    """Project <- 'Main Database'. Ez a legnagyobb/legzajosabb tábla (~140 mező) - a
    felhasználó döntése alapján (2026-07-02) minden mező saját oszlopot kap (lásd
    app/models/project.py), nincs közös 'extra' JSON. Crew-t (stáb) NEM tudunk
    hozzárendelni, mert az 'Operatőr' mező Notion user-people típusú, nem relation
    az Employee-forrás táblára - a nyers people-értéket az `operator_notion` oszlop
    őrzi."""
    result = ImportResult(entity_type="Project")
    unknown_project_code = get_or_create_unknown_project_code(db)

    for page in client.query_database(db_ids.MAIN_DATABASE):
        props = extract_properties(page, client)
        nev = _text(props.get("Name"))
        if not nev:
            result.skipped += 1
            continue

        project_code_id = (
            resolve_relation_id(db, "ProjectCode", props.get("HYPE ADMIN projektkódok") or [])
            or unknown_project_code.id
        )
        campaign_id = resolve_relation_id(db, "Campaign", props.get("Kampányok") or [])
        forgatas_datuma, forgatas_datuma_vege = _split_date_range(props.get("Date"))

        project_obj = safe_upsert(
            db,
            result,
            Project,
            "Project",
            page["id"],
            {
                "nev": nev,
                "project_code_id": project_code_id,
                "campaign_id": campaign_id,
                "forgatas_datuma": forgatas_datuma,
                "forgatas_datuma_vege": forgatas_datuma_vege,
                "helyszin": _text(props.get("Helyszín")) or _text(props.get("Location")),
                "allapot": _text(props.get("Állapot")),
                "teljesites_datuma": as_date(props.get("Teljesítés dátuma")),
                "diszpo": _text(props.get("Diszpó")),
                "diszpo_szovege": _text(props.get("Diszpó szövege")),
                "diszpo_pdf_url": props.get("Diszpó pdf"),
                "drive_diszpo_pdf_url": props.get("Drive diszpó pdf"),
                "fo_diszpo_teszteles": props.get("Fő diszpó tesztelés"),
                "fo_diszpo_elozetes_teszteles": props.get("Fő diszpó előzetes tesztelés"),
                "fo_esemenyre_elozetes_kuldes_statusz": _text(props.get("fő eseményre előzetes küldés státusz")),
                "fo_esemenyre_diszpo_kuldes_statusz": _text(props.get("fő eseményre diszpó küldés státusz")),
                "elozetes_diszpo_kuldes": _text(props.get("Előzetes diszpó küldés")),
                "diszpo_teszteles": props.get("Diszpó tesztelés"),
                "elozetes_teszteles": props.get("Előzetes tesztelés"),
                "diszpo_targya_notion": props.get("Diszpó tárgya"),
                "aki_kikuldte_a_diszpot": props.get("Aki kiküldte a diszpót"),
                "aki_az_elozetest_kuldte_ki": props.get("Aki az előzetest küldte ki"),
                "diszpo_iras_kezdete": as_date(props.get("diszpo írás kezdete")),
                "diszpo_iras_vege": as_date(props.get("diszpo írás vége")),
                "diszpo_irasal_toltott_ido": props.get("diszpo írásal töltött idő"),
                "diszpoirassal_toltott_percek": props.get("Diszpóírással töltött percek"),
                "zapier_diszpo_targy": _text(props.get("Zapier diszpo tárgy")),
                "gmail_thread_id": _text(props.get("Gmail Thread ID")),
                "resztvevok_email": _text(props.get("Résztvevők email")),
                "technika_ready": props.get("Technika ready"),
                "vissza_hozott_technika": _text(props.get("Vissza hozott technika")),
                "vissza_nem_kerult_eszkozok": _text(props.get("Vissza nem került eszközök")),
                "berelt_technika_logisztika": _text(
                    props.get("Bérelt, Bérelendő technika és annak a logisztikája")
                ),
                "kivitt_technika": _text(props.get("Kivitt technika")),
                "technika_lista": _text(props.get("Technika lista:")),
                "aki_kivitte_az_eszkozoket": _text(props.get("Aki kivitte az eszközöket")),
                "aki_visszahozta_az_eszkozoket": _text(props.get("Aki visszahozta az eszközöket")),
                "ki_apple_id": _text(props.get("Ki Apple ID")),
                "vissza_apple_id": _text(props.get("Vissza Apple ID")),
                "kivitt_eszkozok_notion_ids": props.get("Kivitt eszközök"),
                "visszahozott_eszkozok_notion_ids": props.get("Visszahozott eszközök"),
                "leltar_notion_ids": props.get("Leltár"),
                "stock_igenyek_1_notion_ids": props.get("Stock igények 1"),
                "archive_technika_projektek_notion_ids": props.get("Archive technika projektek"),
                "szerzodes_allapot": _text(props.get("Szerződés állapot")),
                "megbizott_neve": _text(props.get("Megbízott neve")),
                "megbizott_szekhely": _text(props.get("Megbízott székhely")),
                "megbizott_adoszam": _text(props.get("Megbízott adószám")),
                "kepviselo": _text(props.get("Képviselő")),
                "keltezes_datuma": as_date(props.get("Keltezés dátuma")),
                "megbizas_targya": _text(props.get("Megbízás tárgya")),
                "akiknek_mar_van_tig_szerzodes": props.get("Akiknek már van TIG szerződés"),
                "akiknek_szerzodest_kell_keszitem": props.get("Akiknek szerződést kell készíteni"),
                "mindenkinek_van_szerzodes": props.get("Mindenkinek van szerződés?"),
                "tig_kuldes_idopont": props.get("TIG küldés időpont"),
                "nyilvantartasi_szam": _text(props.get("Nyilvántartási szám:")),
                "alvallakozo_keretszerzodes_notion_ids": props.get("Alvállakozó keretszerződés (külsős)"),
                "szerzodes_keszites_notion_ids": props.get("Szerződés készítés"),
                "akinek_mar_van_notion_ids": props.get("Akinek már van"),
                "netto_osszeg": props.get("Nettó összeg"),
                "start_timer": as_date(props.get("Start timer")),
                "end_timer": as_date(props.get("End timer")),
                "kezdo_datum_notion": props.get("Kezdő dátum"),
                "zaro_datum_notion": props.get("Záró dátum"),
                "forgatas_kezdete_notion": props.get("forgatás kezdete"),
                "forgatas_vege_notion": props.get("forgatás vége"),
                "forgatas_idopontja_notion": props.get("Forgatás időpontja"),
                "tobb_napos": props.get("Több napos"),
                "tobb_napos_szamitas": props.get("több napos számítás"),
                "tobb_napos_test": props.get("több napos test"),
                "hany_nap": props.get("Hány nap"),
                "mai_notion": props.get("Mai?"),
                "jovobeni": props.get("jövőbeni?"),
                "mar_forog_e": props.get("már forog e"),
                "foroge_jelenleg": props.get("foroge jelenleg"),
                "foroge_jelenleg2": props.get("foroge jelenleg2"),
                "darabolas_datuma": as_date(props.get("Darabolás dátuma")),
                "calendar_name": _text(props.get("Calendar Name")),
                "project_name_select": _text(props.get("Project Name")),
                "esemeny": _text(props.get("Esemény")),
                "fo_esemeny_targy_idopont": _text(props.get("fő esemény tárgy időpont")),
                "fo_esemeny_targya": props.get("fő esemény tárgya"),
                "organizer": _text(props.get("Organizer")),
                "attendees_contacts_notion_ids": props.get("Attendees Contacts"),
                "freebusy": _text(props.get("Freebusy")),
                "visibility": _text(props.get("Visibility")),
                "source": _text(props.get("Source")),
                "sync_status": _text(props.get("Sync Status")),
                "automation_name": _text(props.get("Automation Name")),
                "external_id": _text(props.get("external_id")),
                "operator_notion": props.get("Operatőr"),
                "projektkod_szoveg": _text(props.get("Projektkód")),
                "brief": _text(props.get("Brief")),
                "brief_tipus": _text(props.get("Brief típus")),
                "description": _text(props.get("Description")),
                "kontaktok": _text(props.get("Kontaktok")),
                "technikai_kerdes": _text(props.get("Technikai kérdés")),
                "backend_statusz": _text(props.get("Backend státusz")),
                "backend_uzenet": _text(props.get("Backend üzenet")),
                "gyartassal_kapcsolatban": _text(props.get("Gyártással kapcsolatban")),
                "gyartas_komment": _text(props.get("Gyártás komment")),
                "kreativ_doksi_url": props.get("Kreatív doksi"),
                "csatolni_valo": props.get("Csatolni való"),
                "plusz_afa": _text(props.get("PLUSZ áfa")),
                "emailek_notion": props.get("Emailek"),
                "email_notion": props.get("Email"),
                "nincs_email_notion": props.get("nincs email"),
                "fotos_diszpo": props.get("Fotós diszpó"),
                "kreativ_team_database_notion_ids": props.get("Kreatív team database"),
                "visszajelzesek_a_vagoktol_notion_ids": props.get("Visszajelzések a vágóktól"),
                "felvezetett_utomunka_notion_ids": props.get("Felvezetett utómunka"),
                "torolt_anyagok_notion_ids": props.get("Törölt anyagok"),
                "uj_notion": props.get("Új"),
                "altalanos_notion": props.get("Általános"),
                "van_e_utomunka": props.get("Van e utómunka"),
                "duration_hours_notion": props.get("Duration hours(Σ)"),
                "formula_generic": props.get("Formula"),
                "formula_1": props.get("Formula 1"),
                "formula_2": props.get("Formula 2"),
                "sd_akksik": props.get("sd, akksik"),
                "sd_akksik_vege": props.get("sd akksik vége"),
                "created_at_notion": as_datetime(props.get("Created At")),
                "updated_at_notion": as_datetime(props.get("Updated At")),
                "fabian_peter_adott_nap": props.get("Fábián Péter"),
                "barni_adott_nap": props.get("Barni adott nap"),
                "salamon_zalan_adott_nap": props.get("Salamon Zalán adott nap"),
                "iszlai_aron_adott_nap": props.get("Iszlai Áron adott nap"),
                "varga_adam_adott_nap": props.get("Varga Ádám"),
                "hamza_marko_adott_nap": props.get("Hamza Márkó adott nap"),
                "vidor_gergely_adott_nap": props.get("Vidor Gergely"),
                "nemes_attila_adott_nap": props.get("Nemes Attila"),
                "bukfa_kristof_adott_nap": props.get("Bükfa Kristóf"),
                "adott_nap_generic": props.get("adott nap"),
            },
            label=f"Project '{nev}'",
        )

        if project_obj is not None:
            try:
                _link_leltar_equipment(db, project_obj, props)
            except Exception as exc:  # noqa: BLE001 - egy foglalás-feloldási hiba ne vigye el a teljes sort
                result.errors.append(f"Project '{nev}' eszköz-kapcsolat feloldás: {type(exc).__name__}: {exc}")
            try:
                _link_attendees_crew(db, project_obj, props)
            except Exception as exc:  # noqa: BLE001 - egy stáb-feloldási hiba ne vigye el a teljes sort
                result.errors.append(f"Project '{nev}' stáb-kapcsolat feloldás: {type(exc).__name__}: {exc}")

    return result


def import_deliverables(client: NotionClient, db: Session) -> ImportResult:
    """Deliverable <- 'Utómunka'."""
    result = ImportResult(entity_type="Deliverable")

    for page in client.query_database(db_ids.UTOMUNKA):
        props = extract_properties(page, client)
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
                "tobb_vinyo": props.get("Több vinyó"),
                "timesheet_status": _text(props.get("Timesheet status")),
                "stop_timer": props.get("Stop timer"),
                "completed_notion": props.get("Completed"),
                "time_minutes": props.get("Time (minutes)") if isinstance(props.get("Time (minutes)"), (int, float)) else None,
                "jovairva": props.get("jóváírva"),
                "total_time": _text(props.get("Total time")),
                "anyag_zapierbe": props.get("Anyag zapierbe"),
                "updated_at_notion": as_datetime(props.get("Last edited time")),
                "vinyok": props.get("Vinyók"),
                "projektkod_szoveg": _text(props.get("Projektkód")),
                "completed_time": as_date(props.get("Completed time")),
                "vagas_leiras": _text(props.get("Vágás leírás")),
                "aki_felvezette_az_utomunkat_notion_ids": props.get("Aki felvezette az utómunkát"),
                "jovairando_pont": props.get("jóváírandó pont") if isinstance(props.get("jóváírandó pont"), (int, float)) else None,
                "timesheet_public_notion_ids": props.get("Timesheet Public"),
                "timesheet_private_notion_ids": props.get("Timesheet Private"),
                "forgatas_datuma_notion": _text(props.get("Forgatás dátuma")),
                "esemeny_neve": _text(props.get("Esemény neve")),
                "aki_ellenorzesbe_tette_notion_ids": props.get("Aki ellenőrzésbe tette 1"),
                "megrendeloi_email_cimek": _text(props.get("Megrendelői email címek")),
                "email_megnevezes": _text(props.get("Email megnevezés")),
                "megrendeloi_kontaktok_notion_ids": props.get("Megrendelői kontaktok"),
                "archivalas": _text(props.get("Archiválás")),
                "label": _text(props.get("Label")),
                "assigned_to_notion": props.get("Assigned To"),
                "visszajelzessek_notion_ids": props.get("Visszajelzéssek"),
                "files_vagashoz_urls": props.get("Files vágáshoz"),
                "esedekes": _text(props.get("Esedékes")),
                "email_forgatas_datum": _text(props.get("Email forgatás dátum")),
                "xp": _text(props.get("XP")),
                "pontozas": props.get("Pontozás") if isinstance(props.get("Pontozás"), (int, float)) else None,
                "egyeb_megjegyzes": _text(props.get("Egyéb megjegyzés")),
                "nyersanyag_felhasznalhatosaga": props.get("Nyersanyag felhasználhatósága")
                if isinstance(props.get("Nyersanyag felhasználhatósága"), (int, float))
                else None,
                "technikai_helyesseg": props.get("Technikai helyesség")
                if isinstance(props.get("Technikai helyesség"), (int, float))
                else None,
                "kreativ_es_kepi_vilag": props.get("Kreatív és képi világ")
                if isinstance(props.get("Kreatív és képi világ"), (int, float))
                else None,
            },
            label=f"Deliverable '{projekt_neve}'",
        )

    return result


def _numeric_or_none(value: object) -> float | None:
    return value if isinstance(value, (int, float)) else None


def _import_timesheet_database(
    client: NotionClient, db: Session, database_id: str, result: ImportResult, deliverable_relation_field: str
) -> None:
    for page in client.query_database(database_id):
        props = extract_properties(page, client)
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
                "person_notion": props.get("Person"),
                "fut": props.get("fut"),
                "orabere": _numeric_or_none(props.get("Órabér")),
                "timesheet_status": _text(props.get("Timesheet status")),
                "nev": _text(props.get("Name")),
                "time_xp": _text(props.get("Time XP")),
                "time_szoveg": _text(props.get("Time")),
                "time_minutes": _numeric_or_none(props.get("Time (minutes)")),
                "xp_pontozas": _numeric_or_none(props.get("XP pontozás")),
                "vagok_notion_ids": props.get("Vágók"),
                "mai_percek": _numeric_or_none(props.get("Mai percek")),
                "percek_2025_majus": _numeric_or_none(props.get("2025 május percek")),
                "mai_xp": _numeric_or_none(props.get("Mai xp")),
                "kezdes_ma": props.get("kezdés ma"),
                "akkori_orabere": _numeric_or_none(props.get("Akkori órabér")),
                "timesheet_public_notion_ids": props.get("Timesheet Public"),
                "percek_lista": props.get("percek"),
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


def _expense_notion_fields(props: dict) -> dict:
    """A 'Kiadások' / 'Projekt kiadások' / 'Belsős extra kiadások' Notion táblák
    maradék mezői - mindhárom forrás ugyanezen a dict-en megy át, a props.get()
    egyszerűen None-t ad azokra a kulcsokra, amik az adott forrásban nem léteznek."""
    return {
        "letrehozta_notion": props.get("Created by"),
        "afa_osszege": _numeric_or_none(props.get("ÁFÁ összege")),
        "szamla": _text(props.get("Számla")),
        "kiadas_megnevezese_projekt_kod": _text(props.get("Kiadás megnevezése/Project kód")),
        "netto_forintban_notion": _numeric_or_none(props.get("Nettó forintban")),
        "fizetes_datuma": as_date(props.get("Fizetés dátuma")),
        "mikor_fizetett": _text(props.get("Mikor fizetett")),
        "szamla_pdf_urls": props.get("Számla pdf"),
        "plusz_afa": _text(props.get("+ÁFA")),
        "hozzaadas_a_kiadasokhoz": props.get("Hozzá adás a kiadásokhoz"),
        "forintban_notion": _numeric_or_none(props.get("Forintban")),
        "kiadas_datuma": as_date(props.get("Kiadás dátuma")),
        "projekt_kiadasok_notion_ids": props.get("Projekt kiadások"),
        "kiadasok_notion_ids": props.get("Kiadások"),
        "szamla_statusza": _text(props.get("Számla státusza")),
        "fedezes": _text(props.get("Fedezés")),
        "osszes_kiadas_notion": _numeric_or_none(props.get("Összes kiadás")),
        "tulora_osszege": _numeric_or_none(props.get("Túlóra összege")),
        "plusz_afa_mezo": _text(props.get("Plusz Áfa")),
        "arfolyam": _numeric_or_none(props.get("Árfolyam")),
        "datum_notion": props.get("Dátum"),
        "projektkod_notion": props.get("Projektkód"),
        "egyeb_kiadas": props.get("Egyéb kiadás"),
        "tulora_orabere": _numeric_or_none(props.get("Túlóra órabér")),
        "tulora_szama": _numeric_or_none(props.get("Túlóra száma")),
        "egyeni_afa_osszege": _numeric_or_none(props.get("Egyéni áfa összege")),
        "megjegyzes": _text(props.get("Megjegyzés")),
        "plusz_napok_ara": _numeric_or_none(props.get("Plusz napok ára")),
        "plusz_napok_szama": _numeric_or_none(props.get("Plusz napok száma")),
    }


def import_expenses(client: NotionClient, db: Session) -> ImportResult:
    """Expense <- 'Kiadások' + 'Projekt kiadások' + 'Belsős extra kiadások'."""
    result = ImportResult(entity_type="Expense")

    for page in client.query_database(db_ids.KIADASOK):
        props = extract_properties(page, client)
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
                **_expense_notion_fields(props),
            },
            label=f"Expense '{megnevezes}'",
        )

    for page in client.query_database(db_ids.PROJEKT_KIADASOK):
        props = extract_properties(page, client)
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
                **_expense_notion_fields(props),
            },
            label=f"Expense '{megnevezes}'",
        )

    for page in client.query_database(db_ids.BELSOS_EXTRA_KIADASOK):
        props = extract_properties(page, client)
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
                **_expense_notion_fields(props),
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
        props = extract_properties(page, client)
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
                "nev": _text(props.get("Name")),
                "forint_netto_notion": _numeric_or_none(props.get("Forint nettó")),
                "plusz_afa": _text(props.get("+ÁFA")),
                "mikor_fizetett": _text(props.get("Mikor fizetett")),
                "megjegyzes": _text(props.get("Megjegyzés")),
                "arfolyam": _numeric_or_none(props.get("Árfolyam")),
            },
            label=f"Revenue (project_code_id={project_code_id})",
        )

    return result


def import_kp_forgalom(client: NotionClient, db: Session) -> ImportResult:
    """KpForgalom <- 'KP forgalom', a 'Projekt kiadások' relation alapján Expense-hez kötve."""
    result = ImportResult(entity_type="KpForgalom")

    for page in client.query_database(db_ids.KP_FORGALOM):
        props = extract_properties(page, client)
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
                "kiadas_sum_notion": _numeric_or_none(props.get("Kiadás sum")),
                "forintban_notion": _numeric_or_none(props.get("Forintban")),
                "megnevezes": _text(props.get("Megnevezés")),
            },
            label="KpForgalom",
        )

    return result


def import_feedback(client: NotionClient, db: Session) -> ImportResult:
    """Feedback <- 'Visszajelzéssek'. Ha a Deliverable relation nem oldható fel, a sort
    kihagyjuk (Feedback.deliverable_id NOT NULL)."""
    result = ImportResult(entity_type="Feedback")

    for page in client.query_database(db_ids.VISSZAJELZESSEK):
        props = extract_properties(page, client)
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
