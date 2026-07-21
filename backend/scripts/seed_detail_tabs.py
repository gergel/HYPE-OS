"""Kezdeti (admin által később átrendezhető) fül-elrendezés feltöltése a
detail_tab_configs táblába - a Projekt részletnézet már meglévő, kézzel
kurátort 5 fülre bontását viszi át adatbázisba (lásd korábban
frontend/app/(app)/projektek/[id]/page.tsx TAB_FIELDS), a többi entitáshoz
pedig egyetlen "Adatok" fület hoz létre az összes mezővel (a jelenlegi,
fülek nélküli viselkedést tükrözve) - admin ezután a Beállítások oldalon
tetszőlegesen átrendezheti/feldarabolhatja.

Idempotens: entitástípusonként csak akkor ír, ha MÉG NINCS egyetlen sora sem
(hogy egy már admin által testre szabott elrendezést újrafuttatáskor ne írjon
felül).

Használat:  python scripts/seed_detail_tabs.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.detail_tab import DetailTabConfig  # noqa: E402
from app.services.entity_registry import ENTITY_MODELS  # noqa: E402

# A Projekt modell már meglévő szemantikus tagolása (lásd models/project.py
# szekció-kommentjei) - a "csapat" és a szintetikus "_other" (Egyéb) fület a
# frontend adja hozzá mindig (lásd DetailTabs komponens), ezért itt nem
# szerepelnek.
PROJECT_TABS: list[dict] = [
    {
        "tab_key": "overview",
        "label": "Áttekintés",
        "icon": "Info",
        "field_keys": [
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
    },
    {
        "tab_key": "diszpo",
        "label": "Diszpó",
        "icon": "Send",
        "field_keys": [
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
    },
    {
        "tab_key": "technika",
        "label": "Technika",
        "icon": "Wrench",
        "field_keys": [
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
    },
    {
        "tab_key": "penzugy",
        "label": "Szerződés & Pénzügyek",
        "icon": "Wallet",
        "field_keys": [
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
    },
    {
        "tab_key": "kommunikacio",
        "label": "Kommunikáció",
        "icon": "MessagesSquare",
        "field_keys": ["kontaktok", "gyartassal_kapcsolatban", "gyartas_komment", "kreativ_doksi_url", "csatolni_valo", "fo_esemeny_targy_idopont"],
    },
]

# Ezeket a mezőket a Projekt "Egyéb" fülön SEM akarjuk látni - vagy mert
# külön UI kezeli (m2m/FK), vagy mert a lenti field_keys valamelyike
# tartalmazza (lásd ALWAYS_HIDDEN a frontenden).
PROJECT_ALWAYS_HIDDEN = {
    "id",
    "created_at",
    "updated_at",
    "project_code_id",
    "campaign_id",
    "crew_employee_ids",
    "szerzodes_keszites_employee_id",
    "alvallakozo_keretszerzodes_contract_id",
}


def seed(db) -> None:
    for entity_type, model in ENTITY_MODELS.items():
        existing = db.scalar(select(DetailTabConfig.id).where(DetailTabConfig.entity_type == entity_type))
        if existing is not None:
            print(f"  {entity_type}: már van fül-konfigurációja, kihagyva")
            continue

        if entity_type == "project":
            rows = [
                DetailTabConfig(
                    entity_type="project",
                    tab_key=t["tab_key"],
                    label=t["label"],
                    icon=t["icon"],
                    sort_order=index,
                    field_keys=t["field_keys"],
                )
                for index, t in enumerate(PROJECT_TABS)
            ]
        else:
            all_fields = [name for name in model.__table__.columns.keys() if name not in ("id", "created_at", "updated_at")]
            rows = [
                DetailTabConfig(
                    entity_type=entity_type,
                    tab_key="adatok",
                    label="Adatok",
                    icon="Info",
                    sort_order=0,
                    field_keys=all_fields,
                )
            ]
        db.add_all(rows)
        print(f"  {entity_type}: {len(rows)} fül létrehozva")

    db.commit()


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
    print("Kész.")
