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
from app.notion_import import database_ids as db_ids, files
from app.notion_import.client import NotionClient, as_date, as_datetime, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, safe_upsert, upsert

UNKNOWN_CLIENT_KEY = "client:unknown-notion-import"


def _first_url(ertekek: list | None) -> str | None:
    return ertekek[0] if ertekek else None


def _text(value) -> str | None:
    """Üres string helyett None-t ad vissza, hogy ne írjunk felül értelmes mezőket üressel."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _mezo(props: dict, *nevek: str):
    """Az első NEM ÜRES érték a felsorolt mezőnevek közül.

    A HYPE Notion tábláiban ugyanaz az adat több írásmóddal is szerepel
    ("Vállakozás neve" / "Vállalkozás neve", "Vállakozás székhely" /
    "Vállalkozás székhelye") - egy elgépelt oszlopnév miatt ne vesszen el a
    cégadat."""
    for nev in nevek:
        if nev in props:
            ertek = props[nev]
            if ertek not in (None, "", []):
                return ertek
    return None


def _szoveg_mezo(props: dict, *nevek: str) -> str | None:
    return _text(_mezo(props, *nevek))


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

        munkatars = safe_upsert(
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
                "vallalkozas_kepviselo": _szoveg_mezo(props, "Vállalkozás képviselő", "Vállalkozás képviselője", "Vállakozás képviselő"),
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
                "megbizas_targya": _szoveg_mezo(props, "Megbízás tárgya", "Megbizas targya"),
                "szallito_notion_ids": props.get("Szállító"),
                "keltezes_datuma": as_date(props.get("Keltezés dátuma")),
                "archive_technika_elhagyas_notion_ids": props.get("Archive technika elhagyás"),
                "nyilvantartasi_szam": _szoveg_mezo(props, "Nyilvántartási szám:", "Nyilvántartási szám", "Vállalkozás nyilvántartási szám"),
                "vallakozas_szekhely": _szoveg_mezo(props, "Vállakozás székhely", "Vállalkozás székhelye", "Vállalkozás székhely", "Székhely"),
                "van_e_email_cime_notion": props.get("van e email címe"),
                "vallakozas_neve": _szoveg_mezo(props, "Vállakozás neve", "Vállalkozás neve", "Cég neve"),
                "phone_2": props.get("Phone 2"),
                "megjegyzes": _text(props.get("MEGJEGYZÉS")),
                "honnan_ismerjuk": _text(props.get("HONNAN ISMERJÜK")),
                "birthday": as_date(props.get("Birthday")),
                "kiadas_projektkodja_notion_ids": props.get("Kiadás projektkódja"),
                "formula_2_notion": props.get("Formula 2"),
                "main_database_notion_ids": props.get("📅 Main Database"),
                "vallalkozas_adoszama": _szoveg_mezo(props, "Vállalkozás adószáma", "Vállakozás adószáma", "Adószám"),
                "plusz_afa": _text(props.get("Plusz ÁFA")),
            },
            label=f"Employee '{full_name}'",
        )
        if munkatars is not None:
            ujak = files.atemel_mindent(db, props, entity_type="employee", entity_id=munkatars.id, result=result)
            munkatars.photo_url = files.elso(ujak, "Photo") or munkatars.photo_url

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

        feladat_rekord = safe_upsert(
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
        if feladat_rekord is not None:
            ujak = files.atemel_mindent(db, props, entity_type="task", entity_id=feladat_rekord.id, result=result)
            if "Csatolni való" in ujak:
                feladat_rekord.csatolni_valo_urls = ujak["Csatolni való"]
            if "Files & media" in ujak:
                feladat_rekord.files_media_urls = ujak["Files & media"]


def import_tasks(client: NotionClient, db: Session) -> ImportResult:
    """Task <- TEENDŐK + Ági to do list + HYPE TO-DO LIST + Archive feladatok (status=archived)."""
    result = ImportResult(entity_type="Task")
    _import_task_database(client, db, db_ids.TEENDOK, result)
    _import_task_database(client, db, db_ids.AGI_TODO_LIST, result)
    _import_task_database(client, db, db_ids.HYPE_TODO_LIST, result)
    _import_task_database(client, db, db_ids.ARCHIVE_FELADATOK, result, forced_allapot="archived")
    return result


# A "Külsős és belsős" tábla cégadat-mezői - több írásmóddal is előfordulnak.
CEG_NEV_MEZOK = ("Vállakozás neve", "Vállalkozás neve", "Cég neve")
CEG_SZEKHELY_MEZOK = ("Vállakozás székhely", "Vállalkozás székhelye", "Vállalkozás székhely", "Székhely")
CEG_ADOSZAM_MEZOK = ("Vállalkozás adószáma", "Vállakozás adószáma", "Adószám")
CEG_KEPVISELO_MEZOK = ("Vállalkozás képviselő", "Vállalkozás képviselője", "Vállakozás képviselő")
CEG_NYILVANTARTAS_MEZOK = ("Nyilvántartási szám:", "Nyilvántartási szám", "Vállalkozás nyilvántartási szám")
CEG_MEGBIZAS_MEZOK = ("Megbízás tárgya",)
CEG_EMAIL_MEZOK = ("E-MAIL CÍM", "Email")
CEG_KELTEZES_MEZOK = ("Keltezés dátuma", "Keltezés")

# A munkatárs oldalán a keretszerződés relationje - innen tudjuk, melyik
# szerződés-lap kihez tartozik akkor is, ha a szerződés-lapon nincs (vagy más
# néven van) a visszamutató kapcsolat.
EMPLOYEE_SZERZODES_RELATIO = (
    "Alvállakozó keretszerződés (külsős)",
    "Alvállalkozó keretszerződés (külsős)",
    "Alvállakozó keretszerződés",
    "Alvállalkozói keretszerződés",
    "Keretszerződés",
)

# A szerződés-lap oldalán a munkatárs relationje.
SZERZODES_SZEMELY_MEZOK = ("Vállalkozó", "Külsős ", "Külsős", "Személy", "Munkatárs", "Külsős és belsős", "Név")


def _kulsos_es_belsos_oldalak(client: NotionClient) -> list[tuple[dict, dict]]:
    """A 'Külsős és belsős' tábla sorai (oldal + kiolvasott mezők) - a
    szerződés-import két helyen is használja: innen jön a szerződés->munkatárs
    párosítás és a cégadat/PDF is."""
    return [(page, extract_properties(page, client)) for page in client.query_database(db_ids.KULSOS_ES_BELSOS)]


def _szerzodes_munkatars_index(db: Session, oldalak: list[tuple[dict, dict]]) -> dict[str, int]:
    """Szerződés-lap Notion ID -> a mi munkatárs-azonosítónk, a MUNKATÁRS
    felől nézve (lásd EMPLOYEE_SZERZODES_RELATIO). Ez a legmegbízhatóbb
    kapocs: a "Külsős és belsős" táblában mindenkinél ott a saját
    keretszerződése."""
    index: dict[str, int] = {}
    for page, props in oldalak:
        employee_id = resolve_relation_id(db, "Employee", [page["id"]])
        if employee_id is None:
            continue
        for nev in EMPLOYEE_SZERZODES_RELATIO:
            ertek = props.get(nev)
            if isinstance(ertek, list):
                for szerzodes_page_id in ertek:
                    if isinstance(szerzodes_page_id, str) and szerzodes_page_id:
                        index.setdefault(szerzodes_page_id, employee_id)
    return index


def _szerzodes_munkatarsai(db: Session, page: dict, props: dict, index: dict[str, int]) -> list[int]:
    """Kikhez tartozik ez a szerződés-lap - MINDENKIHEZ, nem csak az elsőhöz.

    A Notion "Alvállakozó keretszerződés (külsős)" tábláján a Name mező a CÉG,
    amivel szerződünk, a "Személy" relation pedig az(ok) az ember(ek), aki(k)
    ezen a cégen keresztül dolgozik/dolgoznak - és ugyanarra a cégre KETTEN is
    szerződhetnek. Ha csak az elsőt vennénk, a másodiknak sehol nem lenne
    keretszerződése, és az utókövetés eseti szerződést kérne tőle."""
    talalatok: list[int] = []

    def hozzaad(employee_id: int | None) -> None:
        if employee_id is not None and employee_id not in talalatok:
            talalatok.append(employee_id)

    hozzaad(index.get(page["id"]))
    for nev in SZERZODES_SZEMELY_MEZOK:
        ertek = props.get(nev)
        if isinstance(ertek, list):
            for page_id in ertek:
                if isinstance(page_id, str) and page_id:
                    hozzaad(resolve_relation_id(db, "Employee", [page_id]))
    if not talalatok:
        # Végső próbálkozás: BÁRMELY relation, ami munkatársra oldható fel -
        # enélkül a fel nem oldott szerződés sehol nem látszana.
        for ertek in props.values():
            if isinstance(ertek, list) and ertek and all(isinstance(v, str) for v in ertek):
                hozzaad(resolve_relation_id(db, "Employee", ertek))
                if talalatok:
                    break
    return talalatok


def _tarsult_keretszerzodes(db: Session, result: ImportResult, employee_id: int, mintarol: Contract) -> None:
    """A cégre szerződő TÖBBI ember keretszerződésének frissítése.

    Egy Contract sor egy emberhez tartozik, a Notion-lap viszont a céget írja
    le, amin ketten is lehetnek. Ha a másodiknak MÁR van keretszerződése,
    kiegészítjük a lap adataiból - de újat nem nyitunk neki: a
    keretszerződések köre kézzel karbantartott, az import nem vesz fel új
    embert (lásd import_contracts)."""
    from sqlalchemy import select

    mezok = {
        "ceg_neve": mintarol.ceg_neve,
        "szekhely": mintarol.szekhely,
        "adoszam": mintarol.adoszam,
        "megbizas_targya": mintarol.megbizas_targya,
        "szerzodes_file_url": mintarol.szerzodes_file_url,
        "keltezes": mintarol.keltezes,
        "vallalkozas_kepviseloje": mintarol.vallalkozas_kepviseloje,
        "vallalkozas_nyilvantartasi_szam": mintarol.vallalkozas_nyilvantartasi_szam,
        "email": mintarol.email,
        "nev": mintarol.nev,
    }
    meglevo = db.scalar(
        select(Contract).where(
            Contract.employee_id == employee_id,
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.project_id.is_(None),
            Contract.keretszerzodes.is_(True),
        )
    )
    if meglevo is None:
        result.skipped += 1
        return
    try:
        with db.begin_nested():
            for mezo, ertek in mezok.items():
                if ertek is not None and getattr(meglevo, mezo, None) in (None, ""):
                    setattr(meglevo, mezo, ertek)
            # Az ÁLLAPOT frissülhet (ezt a Notion tartja karban), a többi
            # kézzel beírt adatot nem írjuk felül.
            if mintarol.szerzodes_allapota:
                meglevo.szerzodes_allapota = mintarol.szerzodes_allapota
            if mintarol.alairva and not meglevo.alairva:
                meglevo.alairva = True
            result.updated += 1
            db.flush()
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
        result.errors.append(
            f"Keretszerződés (társ, employee_id={employee_id}, cég='{mintarol.ceg_neve}'): {type(exc).__name__}: {exc}"
        )


def _meglevo_keretszerzodes(db: Session, notion_page_id: str, munkatarsak: list[int]) -> Contract | None:
    """A Notion-laphoz tartozó, MÁR MEGLÉVŐ keretszerződés-sor - vagy None.

    A keretszerződések köre kézzel karbantartott: az import nem vesz fel új
    embert és nem is vesz el senkit, csak a már bent lévőkhöz tölt fel fájlt és
    frissít állapotot. Ezért itt sosem hozunk létre sort.

    Két úton találhatjuk meg: a Notion page ID leképezésén (korábbi importból),
    vagy - ha ilyen még nincs - a laphoz tartozó ember meglévő
    keretszerződésén; utóbbi esetben a leképezést is felvesszük, hogy a
    következő futás már közvetlenül megtalálja."""
    from sqlalchemy import select

    from app.models.notion_import import NotionImportMap

    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == notion_page_id))
    if mapping is not None:
        szerzodes = db.get(Contract, mapping.entity_id)
        if szerzodes is not None:
            return szerzodes

    for employee_id in munkatarsak:
        szerzodes = db.scalar(
            select(Contract).where(
                Contract.employee_id == employee_id,
                Contract.tipus == ContractType.ALVALLALKOZOI,
                Contract.project_id.is_(None),
                Contract.keretszerzodes.is_(True),
            )
        )
        if szerzodes is not None:
            if mapping is None:
                db.add(
                    NotionImportMap(
                        notion_page_id=notion_page_id, entity_type="Contract", entity_id=szerzodes.id
                    )
                )
                db.flush()
            return szerzodes
    return None


#: Amit a Notion-lapról ÁTVESZÜNK egy meglévő keretszerződésre. Az állapot és
#: az aláírt papír frissülhet (ezeket a Notionban tartják karban); a cégadatok
#: csak akkor, ha nálunk üresek - amit kézzel beírtak, azt egy import nem
#: írhatja felül.
def _keretszerzodes_frissitese(db: Session, result: ImportResult, szerzodes: Contract, props: dict) -> None:
    kiegeszitheto = {
        "ceg_neve": _szoveg_mezo(props, *CEG_NEV_MEZOK) or _text(props.get("Name")),
        "szekhely": _szoveg_mezo(props, *CEG_SZEKHELY_MEZOK),
        "adoszam": _szoveg_mezo(props, *CEG_ADOSZAM_MEZOK),
        "megbizas_targya": _text(props.get("Megbízás tárgya")),
        "keltezes": as_date(props.get("Keltezés dátuma")),
        "vallalkozas_kepviseloje": _text(props.get("Vállalkozás képviselője")),
        "vallalkozas_nyilvantartasi_szam": _text(props.get("Vállalkozás nyilvántartási szám")),
        "email": _text(props.get("Email")),
        "nev": _text(props.get("Name")),
        "szerzodes_megjegyzes": _text(props.get("Szerződés megjegyzés")),
    }
    try:
        with db.begin_nested():
            for mezo, ertek in kiegeszitheto.items():
                if ertek is not None and getattr(szerzodes, mezo, None) in (None, ""):
                    setattr(szerzodes, mezo, ertek)
            allapot = _text(props.get("Állapot"))
            if allapot:
                szerzodes.szerzodes_allapota = allapot
            # Biztos, ami biztos: ha valahogy mégis eseti sorra mutatna a
            # leképezés, ne léptessük elő keretszerződéssé.
            szerzodes.keretszerzodes = True
            db.flush()
            result.updated += 1
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
        result.errors.append(f"Keretszerződés frissítése (contract_id={szerzodes.id}): {type(exc).__name__}: {exc}")
        return

    # Az aláírt papír FELTÖLTHETŐ a meglévő sorra - ezt kifejezetten kértük.
    # Ha a Notionban nem feltöltött fájl, hanem külső link áll a mezőben, azt
    # az atemel_mindent nem hozza át (nincs mit letölteni), ezért a nyers URL-t
    # is elfogadjuk - de csak ha nálunk még nincs semmi.
    ujak = files.atemel_mindent(db, props, entity_type="contract", entity_id=szerzodes.id, result=result)
    uj_url = files.elso(ujak, "Szerződés aláírva") or (
        _first_url(props.get("Szerződés aláírva")) if not szerzodes.szerzodes_file_url else None
    )
    if uj_url:
        szerzodes.szerzodes_file_url = uj_url
        szerzodes.alairva = True


def _szerzodes_fajl_urlek(props: dict) -> list[str]:
    """A munkatárs lapján lévő szerződés-fájlok URL-jei ("Szerződés aláírva" és
    társai). A mező NEVE alapján válogatunk, mert a HYPE Notion tábláiban
    következetesen megmondja, mi van benne (ugyanaz az elv, mint
    files.kategoria_mezonevbol)."""
    talalatok: list[str] = []
    for nev, ertek in props.items():
        nev_kicsi = nev.lower()
        if "szerződés" not in nev_kicsi and "szerzodes" not in nev_kicsi:
            continue
        jeloltek = [ertek] if isinstance(ertek, str) else ertek if isinstance(ertek, list) else []
        talalatok.extend(u for u in jeloltek if isinstance(u, str) and u.startswith("http"))
    return talalatok


def _eseti_szerzodes_a_munkatarsbol(db: Session, result: ImportResult, page: dict, props: dict) -> None:
    """A munkatárs saját lapján lévő cégadatból és aláírt szerződés-PDF-ből
    álló ESETI megbízási szerződés.

    A "Külsős és belsős" tábla minden emberénél ott a cégneve, székhelye,
    adószáma, és a "Szerződés aláírva" mezőben maga az aláírt PDF. Ez NEM
    keretszerződés: keretszerződése annak van, aki az "Alvállakozó
    keretszerződés (külsős)" táblában szerepel. Ami innen jön, az eseti
    megbízási szerződés (lásd models/contract.py Contract.keretszerzodes).

    Ha a munkatársnak MÁR van álló szerződés-sora (akár a keretszerződés-
    táblából, akár egy korábbi futásból), azt nem duplikáljuk: csak a hiányzó
    mezőit egészítjük ki - amit a rendszerben már beírtak, azt egy import nem
    írja felül. Aki tehát a keretszerződés-táblában is szerepel, annál ez az
    adat a keretszerződéséhez kerül, nem nyit új sort."""
    from sqlalchemy import select

    employee_id = resolve_relation_id(db, "Employee", [page["id"]])
    if employee_id is None:
        return
    employee = db.get(Employee, employee_id)
    if employee is None:
        return

    cegadat = {
        "ceg_neve": _szoveg_mezo(props, *CEG_NEV_MEZOK),
        "szekhely": _szoveg_mezo(props, *CEG_SZEKHELY_MEZOK),
        "adoszam": _szoveg_mezo(props, *CEG_ADOSZAM_MEZOK),
        "vallalkozas_kepviseloje": _szoveg_mezo(props, *CEG_KEPVISELO_MEZOK),
        "vallalkozas_nyilvantartasi_szam": _szoveg_mezo(props, *CEG_NYILVANTARTAS_MEZOK),
        "megbizas_targya": _szoveg_mezo(props, *CEG_MEGBIZAS_MEZOK),
        "email": _szoveg_mezo(props, *CEG_EMAIL_MEZOK),
        "keltezes": as_date(_mezo(props, *CEG_KELTEZES_MEZOK)),
    }
    fajlok = _szerzodes_fajl_urlek(props)
    if not any(cegadat.values()) and not fajlok:
        # Se cégadat, se szerződés-fájl: ennek az embernek nincs mit áthozni.
        return

    szerzodes = db.scalar(
        select(Contract).where(
            Contract.employee_id == employee_id,
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.project_id.is_(None),
        )
    )
    try:
        with db.begin_nested():
            if szerzodes is None:
                szerzodes = Contract(
                    tipus=ContractType.ALVALLALKOZOI,
                    employee_id=employee_id,
                    nev=employee.full_name,
                    **{k: v for k, v in cegadat.items() if v is not None},
                )
                db.add(szerzodes)
                db.flush()
                result.created += 1
            else:
                for mezo, ertek in cegadat.items():
                    if ertek is not None and getattr(szerzodes, mezo, None) in (None, ""):
                        setattr(szerzodes, mezo, ertek)
                db.flush()
                result.updated += 1
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
        result.errors.append(f"Eseti szerződés '{employee.full_name}': {type(exc).__name__}: {exc}")
        return

    # Az aláírt PDF a szerződés-rekordhoz is odakerül (a munkatárs
    # csatolmányai közt is megmarad): a fájlt nem töltjük le még egyszer, a
    # már átemelt tárhely-objektumra vesszük fel a hivatkozást (lásd
    # files.atemel).
    for url in fajlok:
        try:
            with db.begin_nested():
                uj_url = files.atemel(
                    db,
                    url,
                    entity_type="contract",
                    entity_id=szerzodes.id,
                    kategoria="szerzodes",
                    log=result.file_errors.append,
                )
        except Exception as exc:  # noqa: BLE001 - fájlonkénti izoláció
            result.file_errors.append(f"'{employee.full_name}' szerződés-fájlja kimaradt: {type(exc).__name__}: {exc}")
            continue
        if uj_url and uj_url != url:
            result.files_copied += 1
        if uj_url and not szerzodes.szerzodes_file_url:
            szerzodes.szerzodes_file_url = uj_url[:500]
        if uj_url:
            szerzodes.alairva = True


def import_contracts(client: NotionClient, db: Session) -> ImportResult:
    """Contract <- 'Keretszerződés' (tipus=kereto) + 'Alvállakozó keretszerződés
    (külsős)' (tipus=alvallalkozoi) + a 'Külsős és belsős' tábla cégadatai.

    A harmadik forrás azért kell, mert a keretszerződés adatai (cégnév,
    székhely, adószám, és az aláírt PDF a "Szerződés aláírva" mezőben) a
    munkatárs saját lapján is ott vannak - sokaknak CSAK ott."""
    result = ImportResult(entity_type="Contract")
    kulsos_belsos = _kulsos_es_belsos_oldalak(client)
    szerzodes_index = _szerzodes_munkatars_index(db, kulsos_belsos)

    for page in client.query_database(db_ids.KERETSZERZODES):
        props = extract_properties(page, client)
        client_id = resolve_client_via_contact(db, props.get("Akivel szerződünk") or [])
        szerzodes_url = _first_url(props.get("Szerződés"))
        szerzodes = safe_upsert(
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
        if szerzodes is not None:
            ujak = files.atemel_mindent(db, props, entity_type="contract", entity_id=szerzodes.id, result=result)
            szerzodes.szerzodes_file_url = files.elso(ujak, "Szerződés") or szerzodes.szerzodes_file_url

    for page in client.query_database(db_ids.ALVALLALKOZO_KERETSZERZODES):
        props = extract_properties(page, client)
        munkatarsak = _szerzodes_munkatarsai(db, page, props, szerzodes_index)
        # A keretszerződések köre KÉZZEL karbantartott: az import nem vesz fel
        # új embert és nem is vesz el (lásd _meglevo_keretszerzodes).
        szerzodes = _meglevo_keretszerzodes(db, page["id"], munkatarsak)
        if szerzodes is None:
            result.skipped += 1
            result.errors.append(
                f"Alvállalkozói keretszerződés '{_text(props.get('Name')) or page['id']}': KIHAGYVA - a "
                "Keretszerződések köre kézzel karbantartott, az import nem vesz fel új embert. Ha ide "
                "tartozik, vedd fel a Keretszerződések oldalon, és a következő import már frissíti."
            )
            continue
        _keretszerzodes_frissitese(db, result, szerzodes, props)
        # Ugyanarra a cégre ketten is szerződhetnek: a TÖBBIEK sorát is
        # frissítjük - de csak ha már van nekik (újat itt sem nyitunk).
        for tars_id in munkatarsak[1:]:
            _tarsult_keretszerzodes(db, result, tars_id, szerzodes)

    # 3. forrás: a munkatársak saját lapja (cégadat + aláírt PDF) - ez pótolja
    # azokat a keretszerződéseket, amikhez nincs külön szerződés-lap.
    for page, props in kulsos_belsos:
        _eseti_szerzodes_a_munkatarsbol(db, result, page, props)

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

        projektkod_rekord = safe_upsert(
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
        if projektkod_rekord is not None:
            ujak = files.atemel_mindent(
                db, props, entity_type="projectCode", entity_id=projektkod_rekord.id, result=result
            )
            # A megrendelői számla és az aláírt TIG a projektkód két legfontosabb
            # dokumentuma - ezek külön oszlopban is látszanak a felületen, ezért
            # a mostantól állandó, saját linkre írjuk át őket.
            projektkod_rekord.szamla_url = files.elso(ujak, "Számla") or projektkod_rekord.szamla_url
            projektkod_rekord.tig_alairva_url = (
                files.elso(ujak, "TIG aláírva") or projektkod_rekord.tig_alairva_url
            )
            if "További dokumentumok" in ujak:
                projektkod_rekord.tovabbi_dokumentumok = ujak["További dokumentumok"]

    return result
