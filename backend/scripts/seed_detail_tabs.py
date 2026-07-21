"""Alapértelmezett (admin által a Beállítások oldalon szabadon átrendezhető)
fül-elrendezés feltöltése a detail_tab_configs táblába - minden entitáshoz,
aminek van generikus, fület-alapú részletnézete (lásd frontend
lib/detailTabs.tsx), kézzel kurátort, a modell mezőinek Notion-eredetű
szemantikus csoportosítását (lásd az egyes models/*.py fájlok szekció-
kommentjeit) tükröző kezdő fül-bontást ad. Ami egyik itt felsorolt fülhöz
sincs rendelve, az a részletnézeten automatikusan a szintetikus "Egyéb"
fülre esik (lásd services/detail_tabs.OTHER_TAB_KEY) - tipikusan a Notion
formula/rollup/relation-snapshot "maradék mezők", amikhez nincs értelme
kézzel elnevezett fület nyitni.

Idempotens: entitástípusonként csak akkor ír, ha MÉG NINCS egyetlen sora sem
(hogy egy már admin által testre szabott elrendezést újrafuttatáskor ne írjon
felül) - emiatt biztonságos MINDEN induláskor lefuttatni (lásd Dockerfile CMD,
ugyanúgy, mint az `alembic upgrade head`): az első induláskor feltölti az
(akkor még üres) táblát a kezdő elrendezéssel, utána már nem nyúl hozzá.

Használat:  python scripts/seed_detail_tabs.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.detail_tab import DetailTabConfig  # noqa: E402
from app.services import detail_tabs as detail_tabs_service  # noqa: E402
from app.services.entity_registry import ENTITY_MODELS  # noqa: E402


class _Tab:
    __slots__ = ("tab_key", "label", "icon", "field_keys")

    def __init__(self, tab_key: str, label: str, icon: str | None, field_keys: list[str]):
        self.tab_key = tab_key
        self.label = label
        self.icon = icon
        self.field_keys = field_keys


# entity_type -> kézzel kurátort fül-lista. Amit itt nem talál egy entitás,
# az a lenti fallback ágon egyetlen "Adatok" fület kap az összes mezővel
# (a korábbi, fülek nélküli viselkedés) - ez éri a Client-et (csak 5 mezős,
# nem indokolt felbontani) és az Expense/Revenue-t (nincs is generikus
# fület-alapú részletnézetük, lásd penzugyek/* bespoke oldalak).
ENTITY_TABS: dict[str, list[_Tab]] = {
    "project": [
        _Tab(
            "overview",
            "Áttekintés",
            "Info",
            [
                "nev",
                "allapot",
                "forgatas_datuma",
                "forgatas_datuma_vege",
                "helyszin",
                "teljesites_datuma",
                "projektkod_szoveg",
                "brief",
                "brief_tipus",
                "description",
                "calendar_name",
                "organizer",
            ],
        ),
        _Tab(
            "diszpo",
            "Diszpó",
            "Send",
            [
                "diszpo",
                "diszpo_szovege",
                "elozetes_diszpo_kuldes",
                "fo_esemenyre_elozetes_kuldes_statusz",
                "fo_esemenyre_diszpo_kuldes_statusz",
                "diszpo_pdf_url",
                "drive_diszpo_pdf_url",
                "resztvevok_email",
                "fo_diszpo_teszteles",
                "fo_diszpo_elozetes_teszteles",
                "diszpo_teszteles",
                "elozetes_teszteles",
                "diszpo_iras_kezdete",
                "diszpo_iras_vege",
                "diszpoirassal_toltott_percek",
                "fotos_diszpo",
            ],
        ),
        _Tab(
            "technika",
            "Technika",
            "Wrench",
            [
                "technika_ready",
                "berelt_technika_logisztika",
                "technika_lista",
                "kivitt_technika",
                "vissza_hozott_technika",
                "vissza_nem_kerult_eszkozok",
                "aki_kivitte_az_eszkozoket",
                "aki_visszahozta_az_eszkozoket",
                "ki_apple_id",
                "vissza_apple_id",
                "darabolas_datuma",
                "technikai_kerdes",
            ],
        ),
        _Tab(
            "penzugy",
            "Szerződés & Pénzügyek",
            "Wallet",
            [
                "szerzodes_allapot",
                "megbizott_neve",
                "megbizott_szekhely",
                "megbizott_adoszam",
                "kepviselo",
                "keltezes_datuma",
                "megbizas_targya",
                "nyilvantartasi_szam",
                "szerzodes_pdf_url",
                "netto_osszeg",
                "plusz_afa",
            ],
        ),
        _Tab(
            "kommunikacio",
            "Kommunikáció",
            "MessagesSquare",
            ["kontaktok", "gyartassal_kapcsolatban", "gyartas_komment", "kreativ_doksi_url", "csatolni_valo", "fo_esemeny_targy_idopont"],
        ),
    ],
    "projectCode": [
        _Tab(
            "overview",
            "Áttekintés",
            "Info",
            ["projektkod", "datum", "esemeny_allapota", "helyszin", "project_nev", "megjegyzes", "datum_megjegyzes"],
        ),
        _Tab(
            "penzugy",
            "Pénzügy",
            "Wallet",
            [
                "penznem",
                "arfolyam",
                "netto_osszeg",
                "osszesen_netto_notion",
                "netto_notion",
                "brutto_notion",
                "gyartasi_koltseg_notion",
                "osszes_koltseg_notion",
                "belsos_koltseg_notion",
                "belso_plusz_koltseg_notion",
                "belsos_koltseg_akkor",
                "alvallalkozok_koltsege_notion",
                "vagasi_koltseg_notion",
                "profit_szazalek_notion",
                "vallalasi_ar_notion",
                "forintban_notion",
                "megerte_e",
                "bevetel_formaja",
            ],
        ),
        _Tab(
            "szerzodes",
            "Szerződés",
            "FileText",
            [
                "szerzodes_url",
                "szerzodes_targya",
                "szerzodes_specialis_eset",
                "szerzodes_kuldes",
                "szerzodes_plusz_afa",
                "szerzodes_helye",
                "szerzodes_netto_osszeg",
                "szerzodes_statusza",
                "szerzodes_projekt_nev",
                "szerzodes_keltezes_datuma",
                "keltezes_datuma",
                "keltezes_datum_formazva",
                "plusz_afa",
                "megbizas_targya",
                "specialis_eset",
            ],
        ),
        _Tab(
            "teljesites",
            "Teljesítés & TIG",
            "Calendar",
            [
                "teljesites_datuma",
                "teljesites_datum_formazva",
                "teljesites",
                "tig_statusza",
                "tig_teljesitesi_ido",
                "tig_projektnev",
                "tig_kikuldve",
                "tig_specialis",
                "tig_url",
                "tig_alairva_url",
                "fizetesi_hatarido",
                "utalas_datuma",
                "szamla_statusza",
                "szamla_url",
                "adminisztracios_tablaban",
                "darabolva",
            ],
        ),
        _Tab(
            "megrendelo",
            "Megrendelő",
            "Building2",
            [
                "megrendelo_neve",
                "megrendelo_szekhelye",
                "megrendelo_adoszama",
                "megrendelo_nyilvantartasi_szam",
                "megrendelo_kepviseloje",
                "megrendelo_email",
                "megrendeloi_emailek",
            ],
        ),
    ],
    "employee": [
        _Tab(
            "overview",
            "Áttekintés",
            "Info",
            ["full_name", "first_name", "last_name", "tipus", "role", "is_active", "elso_munkanap", "utolso_munkanap", "birthday"],
        ),
        _Tab(
            "kapcsolat",
            "Kapcsolat",
            "Users",
            ["telefon", "phone_2", "linkedin_profile", "twitter_profile", "facebook_profile", "photo_url", "honnan_ismerjuk"],
        ),
        _Tab(
            "munka",
            "Munka & Értékelés",
            "Briefcase",
            [
                "jogositvany",
                "ertekeles",
                "technikai_ismeret",
                "milyen_suru_hivjuk",
                "munkanapok_notion",
                "events_involved_count_notion",
                "hany_visszajelzese_van_notion",
                "legutolso_napi_dij_megegyezes",
                "orabler_notion",
                "napidij_notion",
                "belsos_havi_tig",
            ],
        ),
        _Tab(
            "kiadasok",
            "Kiadások",
            "DollarSign",
            ["extra_kiadas_megnevezes", "extra_kiadas_osszeg", "extra_kiadas_datuma", "netto_osszeg"],
        ),
    ],
    "equipment": [
        _Tab(
            "overview",
            "Áttekintés",
            "Info",
            ["nev", "kategoria", "allapot", "archive_statusz", "track_mode", "osszes_mennyiseg", "serial_number", "hasznalhato", "qr_kod", "qr"],
        ),
        _Tab(
            "tortenet",
            "Történet & Karbantartás",
            "Wrench",
            [
                "rendszerbe_kerules_idopontja",
                "forgatasi_napok",
                "hany_forgatason_vett_reszt",
                "hany_napot_dolgozott",
                "szerviz_leiras",
                "megeri_e_szerelni",
                "selejtezes_elhagyas_datuma",
                "ahol_utoljara_volt",
                "zoom_atfogas",
                "megjegyzes",
                "stock_qty",
            ],
        ),
    ],
    "campaign": [
        _Tab("overview", "Áttekintés", "Info", ["nev", "kampany_statusza", "hatarido", "intervalluma", "kesz", "leiras"]),
        _Tab("utomunka", "Utómunka", "Clapperboard", ["forgatas_utomunka", "forgatas", "van_utomunka", "utomunka_szoveg"]),
    ],
    "task": [
        _Tab("overview", "Áttekintés", "Info", ["feladat", "allapot", "hatarido", "kategoria", "checked", "leiras", "kovetkezo_lepes"]),
        _Tab("info", "Egyéb infó", "FileText", ["ugyfel", "csatolni_valo_urls", "files_media_urls"]),
    ],
    "deliverable": [
        _Tab(
            "overview",
            "Áttekintés",
            "Info",
            ["projekt_neve", "allapot", "hatarido", "esemeny_neve", "projektkod_szoveg", "label", "esedekes", "archivalas"],
        ),
        _Tab(
            "fajlok",
            "Fájlok",
            "FileText",
            ["kesz_anyag_url", "nyersanyag_url", "anyag_kikuldve", "files_vagashoz_urls", "vagas_leiras"],
        ),
        _Tab(
            "penzugy",
            "Pénzügy & Idő",
            "DollarSign",
            ["koltseg", "time_minutes", "completed_time", "jovairva", "jovairando_pont", "timesheet_status"],
        ),
        _Tab(
            "minoseg",
            "Visszajelzés / Minőség",
            "MessagesSquare",
            ["pontozas", "xp", "nyersanyag_felhasznalhatosaga", "technikai_helyesseg", "kreativ_es_kepi_vilag", "egyeb_megjegyzes"],
        ),
    ],
}


def seed(db) -> None:
    for entity_type, model in ENTITY_MODELS.items():
        existing = db.scalar(select(DetailTabConfig.id).where(DetailTabConfig.entity_type == entity_type))
        if existing is not None:
            print(f"  {entity_type}: már van fül-konfigurációja, kihagyva")
            continue

        curated = ENTITY_TABS.get(entity_type)
        if curated is not None:
            tabs = curated
        else:
            all_fields = [name for name in model.__table__.columns.keys() if name not in ("id", "created_at", "updated_at")]
            tabs = [_Tab("adatok", "Adatok", "Info", all_fields)]

        detail_tabs_service.replace_tabs(db, entity_type, tabs)
        print(f"  {entity_type}: {len(tabs)} fül létrehozva")


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
    print("Kész.")
