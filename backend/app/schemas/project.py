from datetime import date, datetime, time

from pydantic import BaseModel, computed_field

JsonScalar = dict | list | float | str | bool | None


class SzerzodesKeszitesPayload(BaseModel):
    employee_id: int


class ProjectBase(BaseModel):
    nev: str
    #: Üres is lehet - lásd models/project.py.
    project_code_id: int | None = None
    campaign_id: int | None = None
    forgatas_datuma: date | None = None
    forgatas_datuma_vege: date | None = None
    #: Forrásonkénti tükör-mezők + kézi zár - lásd models/project.py. A
    #: felület a lenti veg_datum számított mezőt használja, ezek csak a
    #: kiszámításához (és hibakereséshez) utaznak.
    naptar_datum_vege: date | None = None
    notion_datum_vege: date | None = None
    forgatas_datum_kezzel_beallitva: bool = False
    # A forgatás napon belüli időpontja (hánytól hányig) - a naptárból is
    # átjön, lásd services/google_calendar.py.
    forgatas_kezdes_ido: time | None = None
    forgatas_veg_ido: time | None = None
    helyszin: str | None = None
    allapot: str | None = None
    #: A projektkód SZÖVEGE. Létrehozáskor is megadható: ebből keressük meg a
    #: Project Code-ot, hogy a projekt rögtön a helyére kerüljön (lásd
    #: routes/projects._kosd_a_projektkodhoz).
    projektkod_szoveg: str | None = None


class VegDatumSzamitas(BaseModel):
    """A számított veg_datum - CSAK az olvasó sémák (lista + részlet) keverik
    be. A ProjectBase-en volt, de onnan a ProjectCreate is örökölte, a
    model_dump() a számított mezőt is beleteszi, és a Project(**data)
    konstruktor 'invalid keyword argument'-tel elszállt tőle - vagyis
    SEMMILYEN projektet nem lehetett létrehozni a felületről."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def veg_datum(self) -> date | None:
        """A forgatás TÉNYLEGES (megjelenítendő) záró napja - a felület
        mindenhol EZT használja (naptár-sáv, táblázat, dátum-szerkesztő).

        Kézi dátum-zárnál (forgatas_datum_kezzel_beallitva) kizárólag a kézzel
        beállított forgatas_datuma_vege számít - ha az üres, a forgatás
        SZÁNDÉKOSAN egynapos. Zár nélkül az első ismert vég nyer:
        forgatas_datuma_vege -> naptar_datum_vege -> notion_datum_vege
        (a forrásonkénti tükör-oszlopokat kizárólag a saját folyamatuk írja,
        lásd models/project.py - ezért ami egyszer megjött, nem veszhet el).
        A kezdetnél nem későbbi vég nem vég."""
        if self.forgatas_datum_kezzel_beallitva:
            jelolt = self.forgatas_datuma_vege
        else:
            jelolt = self.forgatas_datuma_vege or self.naptar_datum_vege or self.notion_datum_vege
        if jelolt is None or self.forgatas_datuma is None or jelolt <= self.forgatas_datuma:
            return None
        return jelolt


class ProjectCreate(ProjectBase):
    crew_employee_ids: list[int] = []


class ProjectListItem(VegDatumSzamitas, ProjectBase):
    """A projekt lista nézet (GET /api/v1/projects) szűkített sémája - a Project
    ~140 oszlopos teljes ProjectRead helyett, mert a lista oldal ténylegesen csak
    ezt az 5-6 mezőt jeleníti meg (lásd frontend/app/projektek/page.tsx és
    RelatedTable), a teljes séma soronkénti validálása/JSON-ba szerializálása
    pedig érezhetően lassította a listaoldal betöltését sok projekt esetén.

    A diszpó-mezők (diszpo/elozetes_diszpo_kuldes/resztvevok_email) azért
    kerültek ide is, mert a Naptár/Diszpó oldal (lásd frontend
    NaptarDiszpoContent.tsx) a lista végpontból építi fel az áttekintő
    táblázatot/naptárat, és ott soronként meg kell jelenni, kinek van már
    kiküldve az előzetes/teljes diszpója, anélkül hogy projektenként külön
    lekérné a teljes ~140 mezős rekordot."""

    id: int
    diszpo: str | None = None
    elozetes_diszpo_kuldes: str | None = None
    resztvevok_email: str | None = None
    # A Naptár/Diszpó oldalnak tudnia kell, melyik esemény meeting/helyszín-
    # bejárás - azokat nem kell (és nem is lehet) diszponálni.
    nem_diszponalando: bool = False
    naptar_szin: str | None = None
    # Ha ez a sor egy több napos forgatásból LEVÁLASZTOTT nap, akkor itt az
    # eredeti projekt azonosítója - a Naptár/Diszpó nézetnek ebből derül ki,
    # hogy az adott napra már a leválasztott nap a diszponálandó, nem az
    # egész (lásd services/project_actions.create_feldarabolas).
    feldarabolas_szulo_id: int | None = None

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    nev: str | None = None
    campaign_id: int | None = None
    forgatas_datuma: date | None = None
    forgatas_datuma_vege: date | None = None
    forgatas_kezdes_ido: time | None = None
    forgatas_veg_ido: time | None = None
    helyszin: str | None = None
    allapot: str | None = None
    crew_employee_ids: list[int] | None = None
    technika_ready: bool | None = None
    alvallakozo_keretszerzodes_contract_id: int | None = None
    # Kézzel is átállítható: ha valaki elfelejtette lilára tenni a naptárban a
    # meetinget (vagy épp fordítva), ne kelljen a naptárhoz nyúlni miatta.
    nem_diszponalando: bool | None = None


class ProjectRead(VegDatumSzamitas, ProjectBase):
    id: int
    crew_employee_ids: list[int] = []
    google_calendar_event_id: str | None = None
    naptar_szin: str | None = None
    nem_diszponalando: bool = False
    #: Ha ez a projekt egy több napos forgatásból leválasztott nap, itt az
    #: eredeti projekt id-je áll (lásd project_actions.create_feldarabolas).
    feldarabolas_szulo_id: int | None = None

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
    gmail_last_message_id: str | None = None
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
    szerzodes_pdf_url: str | None = None
    szerzodes_keszites_employee_id: int | None = None
    alvallakozo_keretszerzodes_contract_id: int | None = None
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
