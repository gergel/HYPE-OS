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

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.deliverable_comment import DeliverableComment
from app.models.employee import Employee
from app.models.equipment import Assignment
from app.models.feedback import Feedback
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.notion_import import NotionImportMap
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.notion_import import database_ids as db_ids, files
from app.notion_import.client import NotionClient, as_date, as_datetime, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, resolve_relation_ids, safe_upsert
from app.notion_import.importers import _text
from app.services.hu_szoveg import ekezet_nelkul
from app.services import project_matching



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


def _forgatas_tartomany(props: dict) -> tuple:
    """A forgatás TÓL-IG tartománya - TÖBB jelölt Notion-mezőből összerakva.

    A Main Database-ben több dátum-jellegű mező él egymás mellett: a "Date"
    (a 2Sync naptár-tükre - a több napos eseményeknél is gyakran CSAK a kezdő
    napot hordozza), a "Forgatás időpontja", a "Kezdő dátum"/"Záró dátum" pár
    és a "forgatás kezdete"/"forgatás vége" formulák. Hogy melyikben van
    ténylegesen kitöltve a tól-ig, munkaterületenként más - a felhasználó
    Notion-naptár nézete sem feltétlenül a "Date"-re épül. Amíg az import
    KIZÁRÓLAG a "Date"-et olvasta, a több napos forgatások vége el sem
    juthatott hozzánk, ha az a valóságban egy másik mezőben élt (a felhasználó
    2026-08-30-i hibajelzése: "a naptárban/Notionben tól-ig van, mégis csak a
    kezdő dátum jön át").

    A KEZDET az első kitöltött jelöltből jön (a "Date" az elsődleges), a VÉG
    pedig az első olyanból, amelyik egyáltalán ismer véget - így az is
    működik, amikor a kezdet a "Date"-ben, a vég viszont csak a "Záró dátum"
    vagy a "forgatás vége" mezőben van meg. Értelmetlen (a kezdetnél nem
    későbbi) vég nem számít."""

    def egy_datum(value):
        return _split_date_range(value)[0]

    jeloltek = [
        _split_date_range(props.get("Date")),
        _split_date_range(props.get("Forgatás időpontja")),
        (egy_datum(props.get("Kezdő dátum")), egy_datum(props.get("Záró dátum"))),
        (egy_datum(props.get("forgatás kezdete")), egy_datum(props.get("forgatás vége"))),
    ]
    kezdet = next((s for s, _ in jeloltek if s is not None), None)
    veg = next((e for _, e in jeloltek if e is not None), None)
    if kezdet is not None and veg is not None and veg > kezdet:
        return kezdet, veg
    return kezdet, None


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


def _naptari_parjahoz_kotes(
    db: Session, result: ImportResult, page_id: str, nev: str, forgatas_datuma
) -> None:
    """Ha ezt a Notion-oldalt még nem importáltuk, de UGYANAZ a forgatás már
    bent van a naptárból, akkor a Notion-oldalt AHHOZ a projekthez kötjük -
    így a következő lépés (upsert) azt frissíti, nem hoz létre egy másodikat.

    Ez a naptár-szinkron párja: az esemény-oldalról ugyanez történik a
    Notionból már bejött projektekkel (lásd google_calendar._find_unlinked_match)."""
    if db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == page_id)) is not None:
        return
    parja = project_matching.azonos_forgatas(
        db, nev, forgatas_datuma, csak_naptarbol=True, csak_notion_nelkul=True
    )
    if parja is None:
        return
    try:
        with db.begin_nested():
            db.add(NotionImportMap(notion_page_id=page_id, entity_type="Project", entity_id=parja.id))
            db.flush()
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
        result.errors.append(f"Project '{nev}' naptári párjához kötés: {type(exc).__name__}: {exc}")


def _naptar_iker_takaritas(db: Session, result: ImportResult, projekt) -> None:
    """A korábbi futásokból itt maradt naptár-duplikátum összevonása.

    Ha ugyanarra a forgatásra van egy naptárból létrejött MÁSIK sor is, a
    naptáresemény átkerül erre a projektre, a másik pedig törlődik - de CSAK
    ha azon a naptárból jött adatokon kívül nincs semmi. Ha van (pl. már
    csináltak rá utómunkát), meghagyjuk, és kiírjuk a naplóba, hogy kézzel
    nézzék meg."""
    iker = project_matching.azonos_forgatas(
        db, projekt.nev, projekt.forgatas_datuma, kizart_id=projekt.id, csak_naptarbol=True, csak_notion_nelkul=True
    )
    if iker is None:
        return
    try:
        with db.begin_nested():
            beolvasztva = project_matching.olvaszd_be_a_naptar_ikret(db, projekt, iker)
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
        result.errors.append(f"Project '{projekt.nev}' naptár-ikrének összevonása: {type(exc).__name__}: {exc}")
        return
    if not beolvasztva:
        result.errors.append(
            f"Project '{projekt.nev}' ({projekt.forgatas_datuma}): a naptárból van egy másik sor is "
            f"(#{iker.id}), de már dolgoztak rajta, ezért NEM vontuk össze - nézd át kézzel."
        )


# Amit egy import nem üresíthet ki egy naptárhoz kötött projekten (lásd
# _naptar_mezok_vedelme): részben amit csak a NAPTÁR tud (időpont, helyszín,
# szín), részben a forgatás TÓL-IG dátumai. Utóbbi azért kell ide, mert a
# 2Sync által a naptárból Notionbe tükrözött oldal "Date" mezője gyakran csak
# a KEZDŐ napot hordozza - enélkül az import minden futáskor kitörölte a
# naptárból már helyesen megjött forgatas_datuma_vege-t, és a több napos
# forgatások soha nem látszottak több naposnak (a felhasználó 2026-08-30-i
# hibajelzése). Ha a Notion Date-ben TÉNYLEG van tól-ig, az változatlanul
# felülír - a védelem csak az ÜRESSEL írás ellen szól (lásd
# _naptar_mezok_visszaallitasa). Több naposról EGYNAPOSRA rövidíteni ezért a
# HYPE OS felületén (vagy a kezdő dátum áthelyezésével) lehet - lásd még
# services/google_calendar.py azonos irányú védelme.
NAPTAR_SAJAT_MEZOK = (
    "forgatas_datuma",
    "forgatas_datuma_vege",
    "forgatas_kezdes_ido",
    "forgatas_veg_ido",
    "helyszin",
    "description",
    "naptar_szin",
)

#: A KÉZI DÁTUM-ZÁR alá eső mezők (lásd models/project.py
#: forgatas_datum_kezzel_beallitva és routes/projects.py FORGATAS_DATUM_MEZOK):
#: kézzel beállított dátumú projekten az import ezekhez hozzá sem nyúl.
KEZI_ZAR_MEZOK = ("forgatas_datuma", "forgatas_datuma_vege", "forgatas_kezdes_ido", "forgatas_veg_ido")


def _naptar_mezok_vedelme(projekt) -> dict:
    """A naptártól kapott mezők pillanatképe egy naptárhoz kötött projekten.

    A Notion "Main Database"-ben nincs pontos időpont, helyszín és szín - ha
    az import a saját (üres) értékét ráírná, a naptárból jött adat elveszne.
    Az import ATTÓL MÉG felülír mindent, amit a Notion tényleg tud: csak az
    üressel írás ellen véd."""
    if projekt is None or not projekt.google_calendar_event_id:
        return {}
    return {mezo: getattr(projekt, mezo, None) for mezo in NAPTAR_SAJAT_MEZOK}


def _naptar_mezok_visszaallitasa(projekt, mentett: dict) -> None:
    for mezo, ertek in mentett.items():
        if ertek not in (None, "") and getattr(projekt, mezo, None) in (None, ""):
            setattr(projekt, mezo, ertek)


def import_projects(client: NotionClient, db: Session) -> ImportResult:
    """Project <- 'Main Database'. Ez a legnagyobb/legzajosabb tábla (~140 mező) - a
    felhasználó döntése alapján (2026-07-02) minden mező saját oszlopot kap (lásd
    app/models/project.py), nincs közös 'extra' JSON. Crew-t (stáb) NEM tudunk
    hozzárendelni, mert az 'Operatőr' mező Notion user-people típusú, nem relation
    az Employee-forrás táblára - a nyers people-értéket az `operator_notion` oszlop
    őrzi."""
    result = ImportResult(entity_type="Project")

    for page in client.query_database(db_ids.MAIN_DATABASE):
        props = extract_properties(page, client)
        nev = _text(props.get("Name"))
        if not nev:
            result.skipped += 1
            continue

        # Projektkód nélkül a projekt KÖTETLEN marad. Korábban egy gyűjtő
        # ("ISMERETLEN-NOTION-IMPORT") Project Code-ba került, mert a mező
        # kötelező volt - csakhogy a gyűjtő nem válasz, csak egy halom: ami oda
        # kerül, úgy néz ki, mintha el lenne intézve. Ma a mező üres is lehet
        # (lásd services/projektkod_kotes.py), és a projekt akkor kerül a
        # helyére, amikor tényleg megkapja a kódját.
        project_code_id = resolve_relation_id(db, "ProjectCode", props.get("HYPE ADMIN projektkódok") or [])
        campaign_id = resolve_relation_id(db, "Campaign", props.get("Kampányok") or [])
        forgatas_datuma, forgatas_datuma_vege = _forgatas_tartomany(props)

        # Ugyanaz a forgatás lehet, hogy a NAPTÁRBÓL már bejött - akkor azt
        # frissítjük, nem csinálunk másodikat (lásd services/project_matching.py).
        _naptari_parjahoz_kotes(db, result, page["id"], nev, forgatas_datuma)

        # Ha ez a Notion-oldal egy NAPTÁRBÓL jött projektre mutat, a naptár
        # saját adatait (időpont, helyszín, szín) megjegyezzük - az import nem
        # üresítheti ki őket, mert a Notion nem is ismeri ezeket.
        meglevo = db.scalar(
            select(Project)
            .join(NotionImportMap, NotionImportMap.entity_id == Project.id)
            .where(NotionImportMap.entity_type == "Project", NotionImportMap.notion_page_id == page["id"])
        )
        naptar_mezok = _naptar_mezok_vedelme(meglevo)
        # KÉZI DÁTUM-ZÁR (lásd models/project.forgatas_datum_kezzel_beallitva):
        # ha a dátumokat a HYPE OS felületén kézzel állították be, az import a
        # NÉGY dátum-mezőhöz hozzá sem nyúlhat - pillanatképet mentünk, és az
        # upsert után visszaállítjuk (a többi mező változatlanul frissül).
        kezi_zar_datumok = (
            {mezo: getattr(meglevo, mezo) for mezo in KEZI_ZAR_MEZOK}
            if meglevo is not None and meglevo.forgatas_datum_kezzel_beallitva
            else None
        )

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
                # A SAJÁT tükör-oszlop (lásd models/project.notion_datum_vege):
                # pontosan azt tükrözi, amit a Notion mond a forgatás végéről -
                # ezt rajtunk kívül semmi nem írja, ezért ami egyszer megjött,
                # azt más folyamat nem tudja kitörölni (a megjelenített vég a
                # schemas/project.veg_datum számított mezőben áll össze).
                "notion_datum_vege": forgatas_datuma_vege,
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
            _naptar_mezok_visszaallitasa(project_obj, naptar_mezok)
            if kezi_zar_datumok is not None:
                # KÉZI DÁTUM-ZÁR: a kézzel beállított dátumokat az upsert
                # bármit is írt volna, változatlanul visszaállítjuk.
                for mezo, ertek in kezi_zar_datumok.items():
                    setattr(project_obj, mezo, ertek)
            elif naptar_mezok:
                # A forgatás TÓL-IG dátumait a naptárhoz kötött projekten a
                # baseline-védelem (lásd engine._helyben_modositott)
                # MEGKERÜLÉSÉVEL írjuk: ezeket a mezőket a percenkénti
                # naptár-szinkron is írja, amitől az értékük szinte mindig
                # eltér az utolsó import baseline-jától - az upsert ezt tévesen
                # "helyi kézi módosításnak" nézte, és a Notionben megadott
                # tól-ig SOHA nem jött át (a felhasználó 2026-08-30-i
                # hibajelzése). Üressel viszont itt sem törlünk (a 2Sync-tükör
                # Date-je gyakran csak a kezdő nap): amelyik forrás tud a
                # tól-ig-ről, az nyer, üresítés csak kézzel történik.
                if forgatas_datuma is not None:
                    project_obj.forgatas_datuma = forgatas_datuma
                if forgatas_datuma_vege is not None:
                    project_obj.forgatas_datuma_vege = forgatas_datuma_vege
            # Régről itt maradt naptár-iker beolvasztása (a fenti kötés csak az
            # ELSŐ importnál segít; ami korábban duplán jött be, azt itt
            # takarítjuk el).
            _naptar_iker_takaritas(db, result, project_obj)
            try:
                _link_leltar_equipment(db, project_obj, props)
            except Exception as exc:  # noqa: BLE001 - egy foglalás-feloldási hiba ne vigye el a teljes sort
                result.errors.append(f"Project '{nev}' eszköz-kapcsolat feloldás: {type(exc).__name__}: {exc}")
            try:
                _link_attendees_crew(db, project_obj, props)
            except Exception as exc:  # noqa: BLE001 - egy stáb-feloldási hiba ne vigye el a teljes sort
                result.errors.append(f"Project '{nev}' stáb-kapcsolat feloldás: {type(exc).__name__}: {exc}")
            ujak = files.atemel_mindent(db, props, entity_type="project", entity_id=project_obj.id, result=result)
            project_obj.diszpo_pdf_url = files.elso(ujak, "Diszpó pdf") or project_obj.diszpo_pdf_url
            if "Csatolni való" in ujak:
                project_obj.csatolni_valo = ujak["Csatolni való"]

    return result


def _notion_felhasznalo_terkep(client: NotionClient) -> dict[str, dict]:
    """Notion user id -> {"email":.., "nev":..}, EGYSZER lekérve az egész
    workspace-re - a kommentek szerzőjének feloldásához kell (lásd
    _importal_kommenteket), és sokkal olcsóbb, mint kommentenként külön
    /v1/users/{id} hívással. A Notion "bot" típusú szerzőket (automatizált
    integrációk, pl. Zapier) kihagyjuk - azoknak nincs Employee-párjuk."""
    terkep: dict[str, dict] = {}
    for u in client.list_users():
        if u.get("type") != "person":
            continue
        terkep[u["id"]] = {"email": (u.get("person") or {}).get("email"), "nev": u.get("name")}
    return terkep


def _employee_terkepek(db: Session) -> tuple[dict[str, "Employee"], dict[str, "Employee"]]:
    """(email szerint, név szerint) - EGYSZER lekérve, hogy a kommentek
    szerzőjét ne kelljen soronként külön DB-lekérdezéssel keresni."""
    email_szerint: dict[str, Employee] = {}
    nev_szerint: dict[str, Employee] = {}
    for e in db.scalars(select(Employee)).all():
        if e.email:
            email_szerint[e.email.strip().lower()] = e
        if e.full_name:
            nev_szerint[ekezet_nelkul(e.full_name)] = e
    return email_szerint, nev_szerint


def _importal_kommenteket(
    client: NotionClient,
    db: Session,
    result: ImportResult,
    page_id: str,
    deliverable_id: int,
    felhasznalo_terkep: dict[str, dict],
    employee_email_szerint: dict[str, Employee],
    employee_nev_szerint: dict[str, Employee],
    allapot: dict,
) -> None:
    """Egy Utómunka-kártya Notion-beli kommentjeit hozza át a HYPE OS saját
    hozzászólás-chatjébe (lásd models/deliverable_comment.py). A szerzőt a
    Notion user email/név alapján próbáljuk Employee-re feloldani - ha nincs
    egyértelmű találat (pl. külsős/vendég Notion-fiók, vagy egy már törölt
    munkatárs), a komment kimarad, és a `result.skipped` számlálóban látszik,
    nem hallgat el csendben.

    Idempotens: a safe_upsert a komment Notion ID-ja alapján dolgozik, tehát
    egy újrafuttatás nem duplikál, és a HYPE OS-ben azóta módosított
    (helyben szerkesztett) komment szövegét nem írja felül.

    A `/v1/comments` végpont a Notion integráción KÜLÖN "Read comments"
    jogosultságot igényel (nem elég a sima olvasási jog) - ha ez hiányzik, a
    hívás minden egyes kártyánál 403-mal hibázna. Ezt EGYSZER, az ELSŐ ilyen
    hibánál jelezzük a naplóban (nem kártyánként újra és újra), és onnantól a
    futás hátralévő részében meg sem próbáljuk - így egy hiányzó jogosultság
    nem lassítja/téríti el a teljes Utómunka-importot, csak a kommentek
    maradnak ki belőle."""
    if allapot.get("kommentek_letiltva"):
        return
    try:
        kommentek = client.list_comments(page_id)
    except Exception as exc:  # noqa: BLE001 - egy komment-lekérési hiba ne vigye el a teljes Deliverable importot
        if not allapot.get("komment_hiba_jelezve"):
            result.errors.append(
                f"Kommentek lekérése sikertelen (Utómunka #{deliverable_id}): {type(exc).__name__}: {exc} - "
                "ellenőrizd, hogy a Notion integráció kapott-e 'Read comments' jogosultságot. "
                "A további kártyáknál emiatt nem próbálkozunk újra ebben a futásban."
            )
            allapot["komment_hiba_jelezve"] = True
        allapot["kommentek_letiltva"] = True
        return
    for c in kommentek:
        szoveg = "".join(t.get("plain_text", "") for t in c.get("rich_text") or [])
        if not szoveg.strip():
            continue
        szerzo = felhasznalo_terkep.get((c.get("created_by") or {}).get("id"))
        employee = None
        if szerzo:
            email = (szerzo.get("email") or "").strip().lower()
            if email:
                employee = employee_email_szerint.get(email)
            if employee is None and szerzo.get("nev"):
                employee = employee_nev_szerint.get(ekezet_nelkul(szerzo["nev"]))
        if employee is None:
            result.skipped += 1
            continue
        safe_upsert(
            db,
            result,
            DeliverableComment,
            "DeliverableComment",
            c["id"],
            {"deliverable_id": deliverable_id, "employee_id": employee.id, "body": szoveg},
            label=f"Komment (Utómunka #{deliverable_id})",
        )


def import_deliverables(client: NotionClient, db: Session) -> ImportResult:
    """Deliverable <- 'Utómunka', a kártyák alatti kommentekkel együtt (lásd
    _importal_kommenteket) - így az Utómunka oldal hozzászólás-chatje nem csak
    a HYPE OS-ben ezután írt üzeneteket mutatja, hanem a Notion-korabelieket
    is."""
    result = ImportResult(entity_type="Deliverable")
    try:
        felhasznalo_terkep = _notion_felhasznalo_terkep(client)
    except Exception as exc:  # noqa: BLE001 - a workspace-userlista hibája ne vigye el a teljes Deliverable importot
        result.errors.append(
            f"A Notion-felhasználók lekérése sikertelen: {type(exc).__name__}: {exc} - a kommentek szerzője emiatt "
            "nem oldható fel, ezeknél kimarad a komment-átvétel, de az Utómunka-kártyák maguk importálódnak."
        )
        felhasznalo_terkep = {}
    employee_email_szerint, employee_nev_szerint = _employee_terkepek(db)
    komment_allapot: dict = {}

    for page in client.query_database(db_ids.UTOMUNKA):
        props = extract_properties(page, client)
        projekt_neve = _text(props.get("PROJEK NEVE"))
        if not projekt_neve:
            result.skipped += 1
            continue

        koltseg = props.get("Költség")
        utomunka = safe_upsert(
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
        if utomunka is not None:
            ujak = files.atemel_mindent(db, props, entity_type="deliverable", entity_id=utomunka.id, result=result)
            if "Files vágáshoz" in ujak:
                utomunka.files_vagashoz_urls = ujak["Files vágáshoz"]
            _importal_kommenteket(
                client,
                db,
                result,
                page["id"],
                utomunka.id,
                felhasznalo_terkep,
                employee_email_szerint,
                employee_nev_szerint,
                komment_allapot,
            )

    return result


def _numeric_or_none(value: object) -> float | None:
    return value if isinstance(value, (int, float)) else None


def _idopont(value) -> datetime | None:
    """Notion dátum/időpont -> időzóna-tudatos datetime.

    A Notion csak akkor ad időzónát, ha az érték tartalmaz időt is; a puszta
    dátumból (pl. "2025-05-01") naiv datetime lenne. A cél-oszlopok viszont
    timezone-aware-ek, és naiv + aware datetime-ot összehasonlítani hiba -
    ezért az időzóna nélkülieket UTC-nek vesszük."""
    ertek = as_datetime(value)
    if ertek is None:
        return None
    return ertek if ertek.tzinfo is not None else ertek.replace(tzinfo=timezone.utc)


def _veg_datum(props: dict) -> datetime | None:
    """A mérés leállításának időpontja. A Notion tábláiban ugyanez a mező több
    írásmóddal is előfordul ("End Date" / "End date"), ezért mindet megnézzük -
    egy elgépelés miatt ne veszítsük el az adatot.

    Időpontként (és NEM puszta dátumként): a lényeg épp az, hogy MIKOR (hány
    órakor) állították le - a dátumra csonkolás pont ezt dobná el."""
    for kulcs in ("End Date", "End date", "end date", "Vége"):
        ertek = _idopont(props.get(kulcs))
        if ertek is not None:
            return ertek
    return None


def _lezart_idopontok(props: dict) -> tuple[datetime | None, datetime | None]:
    """Egy importált mérés kezdete és VÉGE - a vég mindig ki van töltve.

    A Notionból áthozott mérés sosem lehet "épp fut": a futó mérés azt
    jelenti, hogy valaki MOST dolgozik rajta, és a felület ennek megfelelően
    ketyegteti tovább az időt és a költséget (lásd deliverable_actions.
    get_timer_state - futó az, aminek nincs end_date-je). Egy évekkel ezelőtti
    sorból így napokban mért, több százezer forintos "futó" mérés lett.

    Ezért ha az End Date hiányzik (a Notionban is nyitva maradt a mérő), a
    lezárás időpontját a mért időből számoljuk: kezdés + Time (minutes). Ha az
    sincs, a kezdés pillanatával zárjuk - nulla perc az őszinte válasz, mert
    nem tudjuk, meddig tartott, és semmiképp nem szabad tovább ketyegnie."""
    start = _idopont(props.get("Start Date")) or _idopont(props.get("Start date"))
    vege = _veg_datum(props)
    if vege is not None:
        # Kezdés nélküli, de lezárt sor: a kezdést a mért időből számoljuk
        # vissza, hogy az időtartam ne legyen értelmezhetetlen.
        if start is None:
            percek = _numeric_or_none(props.get("Time (minutes)"))
            start = (vege - timedelta(minutes=float(percek))) if percek else vege
        return start, vege
    if start is None:
        return None, None
    percek = _numeric_or_none(props.get("Time (minutes)"))
    return start, (start + timedelta(minutes=float(percek))) if percek else start


def _meres_kulcsa(employee_id: int, deliverable_id: int | None, start: datetime | None):
    """Egy MÉRÉS azonossága: ki, melyik anyagon, mikor kezdte (percre).

    Ugyanaz az ember ugyanazon az anyagon nem tud két mérést ugyanabban a
    percben indítani - ha mégis két sorunk van rá, az ugyanaz a mérés két
    táblából."""
    return (employee_id, deliverable_id, start.replace(second=0, microsecond=0) if start else None)


def _mar_megvan_publicbol(
    db: Session,
    result: ImportResult,
    page_id: str,
    props: dict,
    kulcs,
    public_page_idk: set[str],
    public_kulcsok: set,
) -> bool:
    """Ez a privát sor ugyanaz a mérés, amit a Public táblából már behoztunk?

    Két jel alapján; az első a biztos: a privát sor "Timesheet Public"
    relationje pont arra a sorra mutat, amit már importáltunk (a két táblát
    Notionban egy szinkron-worker tartotta párban). Ha a relation üres (a
    névalapú párosítás gyakran szakadt), a mérés azonossága dönt.

    Ha egy KORÁBBI import már behozta a duplikátumot, itt töröljük is - így egy
    újrafuttatás magától rendbe teszi a megkettőzött időket."""
    # A relation értéke rendes esetben lista, de éles adatban egyetlen string
    # is előfordul - egy sztringen végigiterálva karakterenként hasonlítanánk.
    parja = props.get("Timesheet Public")
    if isinstance(parja, str):
        parja = [parja]
    elif not isinstance(parja, list):
        parja = []
    duplikatum = any(pid in public_page_idk for pid in parja if isinstance(pid, str))
    if not duplikatum and kulcs[0] is not None and kulcs[2] is not None:
        duplikatum = kulcs in public_kulcsok
    if not duplikatum:
        return False

    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == page_id))
    if mapping is not None:
        regi = db.get(Timesheet, mapping.entity_id)
        if regi is not None:
            db.delete(regi)
        db.delete(mapping)
        db.flush()
    result.skipped += 1
    return True


def _import_timesheet_database(
    client: NotionClient,
    db: Session,
    database_id: str,
    result: ImportResult,
    deliverable_relation_field: str,
    *,
    forras: str,
    leallitasok: dict[int, datetime] | None = None,
    public_page_idk: set[str] | None = None,
    public_kulcsok: set | None = None,
) -> None:
    """`leallitasok`: ha kap egy szótárat, utómunkánként gyűjti a LEGKÉSŐBBI
    leállítási időpontot (End Date). Csak a 'Timesheet Public' táblánál adjuk
    át - a felhasználó kérése szerint az utómunka leállítási ideje onnan jön.

    `public_page_idk` / `public_kulcsok`: a Public táblából már behozott sorok -
    a Public importja tölti fel, a Private importja pedig ezekkel szűri ki a
    kétszer szereplő méréseket (lásd _mar_megvan_publicbol)."""
    for page in client.query_database(database_id):
        props = extract_properties(page, client)
        employee_id = resolve_relation_id(db, "Employee", props.get("Vágó") or [])
        if employee_id is None:
            result.skipped += 1
            continue

        deliverable_id = resolve_relation_id(db, "Deliverable", props.get(deliverable_relation_field) or [])
        # A mérés MINDIG lezárva jön be (lásd _lezart_idopontok). Az utómunka
        # leállítási idejéhez viszont csak a VALÓDI End Date számít - egy
        # számolt lezárás nem "leállítás", azt nem írjuk az utómunkára.
        start, lezaras = _lezart_idopontok(props)
        vege = _veg_datum(props)
        koltseg = props.get("Költség")

        kulcs = _meres_kulcsa(employee_id, deliverable_id, start)
        # A duplikátum-szűrés KIZÁRÓLAG a két tábla között értelmes: a public
        # tábla sorait egymással nem vetjük össze (két külön Notion-sor két
        # külön mérés, akkor is, ha egy percben indultak).
        if forras == "private" and public_page_idk is not None and public_kulcsok is not None:
            if _mar_megvan_publicbol(db, result, page["id"], props, kulcs, public_page_idk, public_kulcsok):
                continue

        safe_upsert(
            db,
            result,
            Timesheet,
            "Timesheet",
            page["id"],
            {
                "employee_id": employee_id,
                "deliverable_id": deliverable_id,
                "start_date": start,
                "end_date": lezaras,
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
                "notion_forras": forras,
            },
            label=f"Timesheet (employee_id={employee_id})",
        )

        if forras == "public":
            # A Private import ezekkel ismeri fel, mi jött már be innen.
            if public_page_idk is not None:
                public_page_idk.add(page["id"])
            if public_kulcsok is not None and kulcs[2] is not None:
                public_kulcsok.add(kulcs)

        if leallitasok is not None and deliverable_id is not None and vege is not None:
            # A LEGKÉSŐBBI leállítás számít: egy utómunkán több mérés is futhatott
            # (több vágó, vagy ugyanaz többször), a kérdés pedig az, mikor
            # állították le utoljára. A tábla sorrendje nem garantált, ezért
            # hasonlítunk, nem egyszerűen felülírunk.
            meglevo = leallitasok.get(deliverable_id)
            if meglevo is None or meglevo < vege:
                leallitasok[deliverable_id] = vege


def import_timesheets(client: NotionClient, db: Session) -> ImportResult:
    """Timesheet <- 'Timesheet Public' + 'Timesheet Private' (a mi sémánkban nincs
    külön visibility mező, a kettő egy egységes Timesheet listába kerül).

    A két Notion-tábla UGYANAZT a mérést is tartalmazhatja: egy szinkron-worker
    tartotta párban őket (lásd docs/hype_os_migration_map.md 5. pont). Ezért a
    Public táblát olvassuk be előbb, és a Private tábla azon sorait, amik
    ugyanaz a mérés, kihagyjuk - különben ugyanaz a munkaidő kétszer számítana
    bele az utómunka összesítésébe (ettől lett egy-egy projekten kétszer annyi
    idő, mint Notionban).

    A 'Timesheet Public' sorai emellett az utómunkára is felírják, mikor
    állították le a vágás mérőjét (Deliverable.vagas_leallitva) - ez az adat az
    Utómunka táblában nincs benne, csak itt, az 'End Date' mezőben."""
    result = ImportResult(entity_type="Timesheet")
    leallitasok: dict[int, datetime] = {}
    public_page_idk: set[str] = set()
    public_kulcsok: set = set()
    _import_timesheet_database(
        client,
        db,
        db_ids.TIMESHEET_PUBLIC,
        result,
        "Utómunka_2",
        forras="public",
        leallitasok=leallitasok,
        public_page_idk=public_page_idk,
        public_kulcsok=public_kulcsok,
    )
    _import_timesheet_database(
        client,
        db,
        db_ids.TIMESHEET_PRIVATE,
        result,
        "Utómunka_1",
        forras="private",
        public_page_idk=public_page_idk,
        public_kulcsok=public_kulcsok,
    )

    # A Timesheet Public a mérvadó forrás: amit ott találtunk, az felülírja a
    # korábbi értéket (akár egy migrációs becslést, akár egy előző futásét) -
    # nem "csak ha későbbi", különben egy téves régi érték örökre beragadna.
    #
    # EGY kivétellel: ha azóta a RENDSZERBEN is dolgoztak az anyagon (van
    # olyan, nem importált mérés, ami később ért véget), akkor az a friss adat
    # - egy import nem tolhatja vissza a leállítást egy évekkel korábbi
    # időpontra. Az importált sorok nem számítanak ilyennek, azok maguk is a
    # Notionból jöttek.
    for deliverable_id, vege in leallitasok.items():
        utomunka = db.get(Deliverable, deliverable_id)
        if utomunka is None:
            continue
        ujabb_sajat = db.scalar(
            select(Timesheet.end_date)
            .where(
                Timesheet.deliverable_id == deliverable_id,
                Timesheet.notion_forras.is_(None),
                Timesheet.end_date.is_not(None),
                Timesheet.end_date > vege,
            )
            .limit(1)
        )
        if ujabb_sajat is None:
            utomunka.vagas_leallitva = vege
    db.flush()
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


def _kiadas_szamlai(db: Session, props: dict, kiadas, result: ImportResult) -> None:
    """A kiadáshoz Notionban feltöltött BEJÖVŐ számlák (a "Számla pdf" mező)
    átemelése az R2-re. Ezek a fájlok kerülnek bele a havi számla-csomagba is
    (lásd routes/finance.py szamlak_zip)."""
    if kiadas is None:
        return
    ujak = files.atemel_mindent(db, props, entity_type="expense", entity_id=kiadas.id, result=result)
    if "Számla pdf" in ujak:
        kiadas.szamla_pdf_urls = ujak["Számla pdf"]


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
        kiadas = safe_upsert(
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
        _kiadas_szamlai(db, props, kiadas, result)

    for page in client.query_database(db_ids.PROJEKT_KIADASOK):
        props = extract_properties(page, client)
        megnevezes = _text(props.get("Kiadás megnevezése"))
        if not megnevezes:
            result.skipped += 1
            continue

        brutto = props.get("Bruttó összeg")
        kiadas = safe_upsert(
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
        _kiadas_szamlai(db, props, kiadas, result)

    for page in client.query_database(db_ids.BELSOS_EXTRA_KIADASOK):
        props = extract_properties(page, client)
        megnevezes = _text(props.get("Megnevezés")) or _text(props.get("Név"))
        if not megnevezes:
            result.skipped += 1
            continue

        kiadas = safe_upsert(
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
        _kiadas_szamlai(db, props, kiadas, result)

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
        bevetel = safe_upsert(
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
        if bevetel is not None:
            # A megrendelőnek kiállított (KIMENŐ) számla a bevétel sorához
            # tartozik - a havi számla-csomag innen szedi össze őket.
            files.atemel_mindent(db, props, entity_type="revenue", entity_id=bevetel.id, result=result)

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
