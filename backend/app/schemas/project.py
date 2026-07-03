from datetime import date, datetime

from pydantic import BaseModel

JsonScalar = dict | list | float | str | bool | None


class ProjectBase(BaseModel):
    nev: str
    project_code_id: int
    campaign_id: int | None = None
    forgatas_datuma: date | None = None
    forgatas_datuma_vege: date | None = None
    helyszin: str | None = None
    allapot: str | None = None


class ProjectCreate(ProjectBase):
    crew_employee_ids: list[int] = []


class ProjectUpdate(BaseModel):
    nev: str | None = None
    campaign_id: int | None = None
    forgatas_datuma: date | None = None
    forgatas_datuma_vege: date | None = None
    helyszin: str | None = None
    allapot: str | None = None
    crew_employee_ids: list[int] | None = None
    technika_ready: bool | None = None


class ProjectRead(ProjectBase):
    id: int
    crew_employee_ids: list[int] = []

    # a 'Main Database' Notion tábla maradék ~140 mezője, egyenként (lásd
    # app/models/project.py) - nem egy közös 'extra' JSON-ban.
    teljesites_datuma: date | None = None
    diszpo: str | None = None
    diszpo_szovege: str | None = None
    diszpo_pdf_url: str | None = None
    drive_diszpo_pdf_url: str | None = None
    fo_diszpo_teszteles: bool | None = None
    fo_diszpo_elozetes_teszteles: bool | None = None
    fo_esemenyre_elozetes_kuldes_statusz: str | None = None
    fo_esemenyre_diszpo_kuldes_statusz: str | None = None
    elozetes_diszpo_kuldes: str | None = None
    diszpo_teszteles: bool | None = None
    elozetes_teszteles: bool | None = None
    diszpo_targya_notion: JsonScalar = None
    aki_kikuldte_a_diszpot: JsonScalar = None
    aki_az_elozetest_kuldte_ki: JsonScalar = None
    diszpo_iras_kezdete: date | None = None
    diszpo_iras_vege: date | None = None
    diszpo_irasal_toltott_ido: JsonScalar = None
    diszpoirassal_toltott_percek: float | None = None
    zapier_diszpo_targy: str | None = None
    gmail_thread_id: str | None = None
    resztvevok_email: str | None = None
    technika_ready: bool | None = None
    vissza_hozott_technika: str | None = None
    vissza_nem_kerult_eszkozok: str | None = None
    berelt_technika_logisztika: str | None = None
    kivitt_technika: str | None = None
    technika_lista: str | None = None
    aki_kivitte_az_eszkozoket: str | None = None
    aki_visszahozta_az_eszkozoket: str | None = None
    ki_apple_id: str | None = None
    vissza_apple_id: str | None = None
    kivitt_eszkozok_notion_ids: JsonScalar = None
    visszahozott_eszkozok_notion_ids: JsonScalar = None
    leltar_notion_ids: JsonScalar = None
    stock_igenyek_1_notion_ids: JsonScalar = None
    archive_technika_projektek_notion_ids: JsonScalar = None
    szerzodes_allapot: str | None = None
    megbizott_neve: str | None = None
    megbizott_szekhely: str | None = None
    megbizott_adoszam: str | None = None
    kepviselo: str | None = None
    keltezes_datuma: date | None = None
    megbizas_targya: str | None = None
    akiknek_mar_van_tig_szerzodes: JsonScalar = None
    akiknek_szerzodest_kell_keszitem: JsonScalar = None
    mindenkinek_van_szerzodes: JsonScalar = None
    tig_kuldes_idopont: JsonScalar = None
    nyilvantartasi_szam: str | None = None
    alvallakozo_keretszerzodes_notion_ids: JsonScalar = None
    szerzodes_keszites_notion_ids: JsonScalar = None
    akinek_mar_van_notion_ids: JsonScalar = None
    netto_osszeg: float | None = None
    start_timer: date | None = None
    end_timer: date | None = None
    kezdo_datum_notion: JsonScalar = None
    zaro_datum_notion: JsonScalar = None
    forgatas_kezdete_notion: JsonScalar = None
    forgatas_vege_notion: JsonScalar = None
    forgatas_idopontja_notion: JsonScalar = None
    tobb_napos: JsonScalar = None
    tobb_napos_szamitas: JsonScalar = None
    tobb_napos_test: JsonScalar = None
    hany_nap: JsonScalar = None
    mai_notion: JsonScalar = None
    jovobeni: JsonScalar = None
    mar_forog_e: JsonScalar = None
    foroge_jelenleg: JsonScalar = None
    foroge_jelenleg2: JsonScalar = None
    darabolas_datuma: date | None = None
    calendar_name: str | None = None
    project_name_select: str | None = None
    esemeny: str | None = None
    fo_esemeny_targy_idopont: str | None = None
    fo_esemeny_targya: JsonScalar = None
    organizer: str | None = None
    attendees_contacts_notion_ids: JsonScalar = None
    freebusy: str | None = None
    visibility: str | None = None
    source: str | None = None
    sync_status: str | None = None
    automation_name: str | None = None
    external_id: str | None = None
    operator_notion: JsonScalar = None
    projektkod_szoveg: str | None = None
    brief: str | None = None
    brief_tipus: str | None = None
    description: str | None = None
    kontaktok: str | None = None
    technikai_kerdes: str | None = None
    backend_statusz: str | None = None
    backend_uzenet: str | None = None
    gyartassal_kapcsolatban: str | None = None
    gyartas_komment: str | None = None
    kreativ_doksi_url: str | None = None
    csatolni_valo: JsonScalar = None
    plusz_afa: str | None = None
    emailek_notion: JsonScalar = None
    email_notion: JsonScalar = None
    nincs_email_notion: JsonScalar = None
    fotos_diszpo: bool | None = None
    kreativ_team_database_notion_ids: JsonScalar = None
    visszajelzesek_a_vagoktol_notion_ids: JsonScalar = None
    felvezetett_utomunka_notion_ids: JsonScalar = None
    torolt_anyagok_notion_ids: JsonScalar = None
    uj_notion: JsonScalar = None
    altalanos_notion: JsonScalar = None
    van_e_utomunka: JsonScalar = None
    duration_hours_notion: JsonScalar = None
    formula_generic: JsonScalar = None
    formula_1: JsonScalar = None
    formula_2: JsonScalar = None
    sd_akksik: JsonScalar = None
    sd_akksik_vege: JsonScalar = None
    created_at_notion: datetime | None = None
    updated_at_notion: datetime | None = None
    fabian_peter_adott_nap: JsonScalar = None
    barni_adott_nap: JsonScalar = None
    salamon_zalan_adott_nap: JsonScalar = None
    iszlai_aron_adott_nap: JsonScalar = None
    varga_adam_adott_nap: JsonScalar = None
    hamza_marko_adott_nap: JsonScalar = None
    vidor_gergely_adott_nap: JsonScalar = None
    nemes_attila_adott_nap: JsonScalar = None
    bukfa_kristof_adott_nap: JsonScalar = None
    adott_nap_generic: JsonScalar = None

    model_config = {"from_attributes": True}
