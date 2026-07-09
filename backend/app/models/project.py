from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

project_crew = Table(
    "project_crew",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("employee_id", ForeignKey("employees.id"), primary_key=True),
)

class Project(TimestampMixin, Base):
    """Konkrét forgatás egy Project Code-on belül.

    A 'Main Database' Notion tábla ~140 mezős - a felhasználó döntése alapján
    (2026-07-02) minden mező saját, névvel ellátott oszlopot kap (nem közös JSON
    "extra"). Kivétel: a puszta Notion buttonök (sosem hordoznak adatot: Fő eseményre
    diszpó, End, Diszpó küldése, Geri forgatás, Feldarabolás, Geri, Start, Fő
    eseményre előzetes diszpó, Utómunka, Előzetes diszpó, szerződés készítése és
    küldése), és a Kampányok/HYPE ADMIN projektkódok relationök, amik már megvannak
    valódi FK-ként (campaign_id/project_code_id).

    Sok mező (formula/rollup/people/relation olyan táblára, amit nem importálunk)
    JSON típusú - a Notion oldali típus futásidőben változhat (pl. egy formula
    lehet szám vagy szöveg is attól függően mit számol), ezért nem lehet előre
    biztonságosan szűkebb SQL típust adni neki anélkül, hogy éles adaton eldőlne.
    A `*_adott_nap` mezők konkrét emberek napi beosztását jelző formulák a régi
    rendszerből - ld. hype_os_migration_map.md 3. fejezet arról, hogy ez a minta
    (személyre szabott mező) miért nem folytatandó a HYPE OS-ben, csak import után
    törlendő technikai adósság."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    forgatas_datuma: Mapped[date | None] = mapped_column(Date)
    forgatas_datuma_vege: Mapped[date | None] = mapped_column(
        Date, comment="A Notion 'Date' property end-je - több napos forgatás záró napja, ha van"
    )
    helyszin: Mapped[str | None] = mapped_column(String(255))
    allapot: Mapped[str | None] = mapped_column(String(50))
    teljesites_datuma: Mapped[date | None] = mapped_column(Date, comment="Teljesítés dátuma")

    # --- diszpó ---
    diszpo: Mapped[str | None] = mapped_column(String(100), comment="Diszpó")
    diszpo_szovege: Mapped[str | None] = mapped_column(Text, comment="Diszpó szövege")
    diszpo_pdf_url: Mapped[str | None] = mapped_column(String(500), comment="Diszpó pdf")
    drive_diszpo_pdf_url: Mapped[str | None] = mapped_column(String(500), comment="Drive diszpó pdf")
    fo_diszpo_teszteles: Mapped[bool | None] = mapped_column(Boolean, comment="Fő diszpó tesztelés")
    fo_diszpo_elozetes_teszteles: Mapped[bool | None] = mapped_column(Boolean, comment="Fő diszpó előzetes tesztelés")
    fo_esemenyre_elozetes_kuldes_statusz: Mapped[str | None] = mapped_column(
        String(100), comment="fő eseményre előzetes küldés státusz"
    )
    fo_esemenyre_diszpo_kuldes_statusz: Mapped[str | None] = mapped_column(
        String(100), comment="fő eseményre diszpó küldés státusz"
    )
    elozetes_diszpo_kuldes: Mapped[str | None] = mapped_column(String(100), comment="Előzetes diszpó küldés")
    diszpo_teszteles: Mapped[bool | None] = mapped_column(Boolean, comment="Diszpó tesztelés")
    elozetes_teszteles: Mapped[bool | None] = mapped_column(Boolean, comment="Előzetes tesztelés")
    diszpo_targya_notion: Mapped[dict | None] = mapped_column(JSON, comment="Diszpó tárgya")
    aki_kikuldte_a_diszpot: Mapped[dict | None] = mapped_column(JSON, comment="Aki kiküldte a diszpót (people)")
    aki_az_elozetest_kuldte_ki: Mapped[dict | None] = mapped_column(
        JSON, comment="Aki az előzetest küldte ki (people)"
    )
    diszpo_iras_kezdete: Mapped[date | None] = mapped_column(Date, comment="diszpo írás kezdete")
    diszpo_iras_vege: Mapped[date | None] = mapped_column(Date, comment="diszpo írás vége")
    diszpo_irasal_toltott_ido: Mapped[dict | None] = mapped_column(JSON, comment="diszpo írásal töltött idő")
    diszpoirassal_toltott_percek: Mapped[float | None] = mapped_column(
        Numeric(10, 2), comment="Diszpóírással töltött percek"
    )
    zapier_diszpo_targy: Mapped[str | None] = mapped_column(String(500), comment="Zapier diszpo tárgy")
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), comment="Gmail Thread ID")
    gmail_last_message_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Az utoljára ebben a diszpó-szálban küldött email RFC822 Message-ID-je (nem Gmail thread ID!) "
        "- ez kell a következő email 'In-Reply-To'/'References' fejlécéhez, hogy az valóban válaszként "
        "(ne külön levélként) fűződjön a szálhoz a címzettek levelezőjében is, nem csak a küldő Gmail-fiókjában.",
    )
    resztvevok_email: Mapped[str | None] = mapped_column(Text, comment="Résztvevők email")
    # A publikus utókövető kérdőív linkjéhez (lásd services/dispo.py,
    # api/routes/public_utokovetes.py) - a diszpó kiküldésekor generáljuk, hogy
    # a bejelentkezést nem igénylő űrlap ne a nyers (kitalálható) project_id-t
    # használja az URL-ben.
    utokoveto_token: Mapped[str | None] = mapped_column(String(64), unique=True)

    # --- technika / eszközök (szöveges/relation mezők - a valódi Equipment/Assignment
    #     kapcsolat az Assignment táblán keresztül él, ezek itt a Notion-oldali nyers adat) ---
    technika_ready: Mapped[bool | None] = mapped_column(Boolean, comment="Technika ready")
    vissza_hozott_technika: Mapped[str | None] = mapped_column(Text, comment="Vissza hozott technika")
    vissza_nem_kerult_eszkozok: Mapped[str | None] = mapped_column(Text, comment="Vissza nem került eszközök")
    berelt_technika_logisztika: Mapped[str | None] = mapped_column(
        Text, comment="Bérelt, Bérelendő technika és annak a logisztikája"
    )
    kivitt_technika: Mapped[str | None] = mapped_column(Text, comment="Kivitt technika")
    technika_lista: Mapped[str | None] = mapped_column(Text, comment="Technika lista:")
    aki_kivitte_az_eszkozoket: Mapped[str | None] = mapped_column(Text, comment="Aki kivitte az eszközöket")
    aki_visszahozta_az_eszkozoket: Mapped[str | None] = mapped_column(Text, comment="Aki visszahozta az eszközöket")
    ki_apple_id: Mapped[str | None] = mapped_column(String(255), comment="Ki Apple ID")
    vissza_apple_id: Mapped[str | None] = mapped_column(String(255), comment="Vissza Apple ID")
    kivitt_eszkozok_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Kivitt eszközök (relation)")
    visszahozott_eszkozok_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Visszahozott eszközök (relation)"
    )
    leltar_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Leltár (relation)")
    stock_igenyek_1_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Stock igények 1 (relation)")
    archive_technika_projektek_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Archive technika projektek (relation)"
    )

    # --- szerződés / TIG ---
    szerzodes_allapot: Mapped[str | None] = mapped_column(String(100), comment="Szerződés állapot")
    megbizott_neve: Mapped[str | None] = mapped_column(String(255), comment="Megbízott neve")
    megbizott_szekhely: Mapped[str | None] = mapped_column(String(500), comment="Megbízott székhely")
    megbizott_adoszam: Mapped[str | None] = mapped_column(String(50), comment="Megbízott adószám")
    kepviselo: Mapped[str | None] = mapped_column(String(255), comment="Képviselő")
    keltezes_datuma: Mapped[date | None] = mapped_column(Date, comment="Keltezés dátuma")
    megbizas_targya: Mapped[str | None] = mapped_column(String(255), comment="Megbízás tárgya")
    akiknek_mar_van_tig_szerzodes: Mapped[dict | None] = mapped_column(
        JSON, comment="Akiknek már van TIG szerződés"
    )
    akiknek_szerzodest_kell_keszitem: Mapped[dict | None] = mapped_column(
        JSON, comment="Akiknek szerződést kell készíteni"
    )
    mindenkinek_van_szerzodes: Mapped[dict | None] = mapped_column(JSON, comment="Mindenkinek van szerződés?")
    tig_kuldes_idopont: Mapped[dict | None] = mapped_column(JSON, comment="TIG küldés időpont")
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100), comment="Nyilvántartási szám:")
    alvallakozo_keretszerzodes_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Alvállakozó keretszerződés (külsős) (relation) - nyers Notion import"
    )
    szerzodes_keszites_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Szerződés készítés (relation) - nyers Notion import"
    )
    akinek_mar_van_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Akinek már van (relation)")
    szerzodes_pdf_url: Mapped[str | None] = mapped_column(
        String(500), comment="Szerződés készítése és küldése gomb - generált szerződés Google Docs linkje"
    )
    szerzodes_keszites_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        comment="'Szerződés készítés' relation (Külsős és belsős) - a kiválasztott ember adatai a "
        "megbízott_* mezőkbe másolódnak (lásd app/services/contract_actions.py)",
    )
    alvallakozo_keretszerzodes_contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contracts.id"),
        comment="'Alvállakozó keretszerződés (külsős)' relation - egy meglévő keretszerződés "
        "hozzálinkelése ehhez a projekthez",
    )

    # --- pénzügy ---
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Nettó összeg")

    # --- forgatás időzítés ---
    start_timer: Mapped[date | None] = mapped_column(Date, comment="Start timer")
    end_timer: Mapped[date | None] = mapped_column(Date, comment="End timer")
    kezdo_datum_notion: Mapped[dict | None] = mapped_column(JSON, comment="Kezdő dátum")
    zaro_datum_notion: Mapped[dict | None] = mapped_column(JSON, comment="Záró dátum")
    forgatas_kezdete_notion: Mapped[dict | None] = mapped_column(JSON, comment="forgatás kezdete")
    forgatas_vege_notion: Mapped[dict | None] = mapped_column(JSON, comment="forgatás vége")
    forgatas_idopontja_notion: Mapped[dict | None] = mapped_column(JSON, comment="Forgatás időpontja")
    tobb_napos: Mapped[dict | None] = mapped_column(JSON, comment="Több napos")
    tobb_napos_szamitas: Mapped[dict | None] = mapped_column(JSON, comment="több napos számítás")
    tobb_napos_test: Mapped[dict | None] = mapped_column(JSON, comment="több napos test")
    hany_nap: Mapped[dict | None] = mapped_column(JSON, comment="Hány nap")
    mai_notion: Mapped[dict | None] = mapped_column(JSON, comment="Mai?")
    jovobeni: Mapped[dict | None] = mapped_column(JSON, comment="jövőbeni?")
    mar_forog_e: Mapped[dict | None] = mapped_column(JSON, comment="már forog e")
    foroge_jelenleg: Mapped[dict | None] = mapped_column(JSON, comment="foroge jelenleg")
    foroge_jelenleg2: Mapped[dict | None] = mapped_column(JSON, comment="foroge jelenleg2")
    darabolas_datuma: Mapped[date | None] = mapped_column(Date, comment="Darabolás dátuma")

    # --- esemény / naptár metaadat ---
    calendar_name: Mapped[str | None] = mapped_column(String(255), comment="Calendar Name")
    project_name_select: Mapped[str | None] = mapped_column(String(255), comment="Project Name (select)")
    esemeny: Mapped[str | None] = mapped_column(Text, comment="Esemény")
    fo_esemeny_targy_idopont: Mapped[str | None] = mapped_column(String(500), comment="fő esemény tárgy időpont")
    fo_esemeny_targya: Mapped[dict | None] = mapped_column(JSON, comment="fő esemény tárgya")
    organizer: Mapped[str | None] = mapped_column(String(255), comment="Organizer")
    attendees_contacts_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Attendees Contacts (relation)")
    freebusy: Mapped[str | None] = mapped_column(String(50), comment="Freebusy")
    visibility: Mapped[str | None] = mapped_column(String(50), comment="Visibility")
    source: Mapped[str | None] = mapped_column(String(100), comment="Source")
    sync_status: Mapped[str | None] = mapped_column(String(100), comment="Sync Status")
    automation_name: Mapped[str | None] = mapped_column(String(100), comment="Automation Name")
    external_id: Mapped[str | None] = mapped_column(String(255), comment="external_id")
    operator_notion: Mapped[dict | None] = mapped_column(JSON, comment="Operatőr (people)")

    # --- projekt/brief adminisztráció ---
    projektkod_szoveg: Mapped[str | None] = mapped_column(String(50), comment="Projektkód (rich_text)")
    brief: Mapped[str | None] = mapped_column(Text, comment="Brief")
    brief_tipus: Mapped[str | None] = mapped_column(String(100), comment="Brief típus")
    description: Mapped[str | None] = mapped_column(Text, comment="Description")
    kontaktok: Mapped[str | None] = mapped_column(Text, comment="Kontaktok")
    technikai_kerdes: Mapped[str | None] = mapped_column(String(500), comment="Technikai kérdés")
    backend_statusz: Mapped[str | None] = mapped_column(String(100), comment="Backend státusz")
    backend_uzenet: Mapped[str | None] = mapped_column(Text, comment="Backend üzenet")
    gyartassal_kapcsolatban: Mapped[str | None] = mapped_column(String(255), comment="Gyártással kapcsolatban")
    gyartas_komment: Mapped[str | None] = mapped_column(Text, comment="Gyártás komment")
    kreativ_doksi_url: Mapped[str | None] = mapped_column(String(500), comment="Kreatív doksi")
    csatolni_valo: Mapped[dict | None] = mapped_column(JSON, comment="Csatolni való (files)")
    plusz_afa: Mapped[str | None] = mapped_column(String(50), comment="PLUSZ áfa")
    emailek_notion: Mapped[dict | None] = mapped_column(JSON, comment="Emailek (rollup)")
    email_notion: Mapped[dict | None] = mapped_column(JSON, comment="Email (formula)")
    nincs_email_notion: Mapped[dict | None] = mapped_column(JSON, comment="nincs email")
    fotos_diszpo: Mapped[bool | None] = mapped_column(Boolean, comment="Fotós diszpó")
    kreativ_team_database_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Kreatív team database (relation)"
    )
    visszajelzesek_a_vagoktol_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="Visszajelzések a vágóktól (relation)"
    )
    felvezetett_utomunka_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Felvezetett utómunka (relation)")
    torolt_anyagok_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Törölt anyagok (relation)")
    uj_notion: Mapped[dict | None] = mapped_column(JSON, comment="Új")
    altalanos_notion: Mapped[dict | None] = mapped_column(JSON, comment="Általános")
    van_e_utomunka: Mapped[dict | None] = mapped_column(JSON, comment="Van e utómunka")
    duration_hours_notion: Mapped[dict | None] = mapped_column(JSON, comment="Duration hours(Σ)")
    formula_generic: Mapped[dict | None] = mapped_column(JSON, comment="Formula")
    formula_1: Mapped[dict | None] = mapped_column(JSON, comment="Formula 1")
    formula_2: Mapped[dict | None] = mapped_column(JSON, comment="Formula 2")
    sd_akksik: Mapped[dict | None] = mapped_column(JSON, comment="sd, akksik")
    sd_akksik_vege: Mapped[dict | None] = mapped_column(JSON, comment="sd akksik vége")

    # --- Notion audit mezők ---
    created_at_notion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Created At")
    updated_at_notion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Updated At")

    # --- "adott nap" mezők: a régi rendszerben egy-egy konkrét emberhez kötött napi
    #     beosztás-formula. Szándékosan nem folytatandó minta (lásd osztály docstring),
    #     de a felhasználó kérésére importáljuk, hogy semmilyen adat ne vesszen el. ---
    fabian_peter_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Fábián Péter")
    barni_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Barni adott nap")
    salamon_zalan_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Salamon Zalán adott nap")
    iszlai_aron_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Iszlai Áron adott nap")
    varga_adam_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Varga Ádám")
    hamza_marko_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Hamza Márkó adott nap")
    vidor_gergely_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Vidor Gergely")
    nemes_attila_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Nemes Attila")
    bukfa_kristof_adott_nap: Mapped[dict | None] = mapped_column(JSON, comment="Bükfa Kristóf")
    adott_nap_generic: Mapped[dict | None] = mapped_column(JSON, comment="adott nap")

    project_code: Mapped["ProjectCode"] = relationship(back_populates="projects")
    campaign: Mapped["Campaign"] = relationship(back_populates="projects")
    crew: Mapped[list["Employee"]] = relationship(secondary=project_crew, back_populates="projects")

    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="project")
    callsheets: Mapped[list["Callsheet"]] = relationship(back_populates="project")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="project")
    media_items: Mapped[list["Media"]] = relationship(back_populates="project")
    folders: Mapped[list["Folder"]] = relationship(back_populates="project")
    portal: Mapped["Portal"] = relationship(back_populates="project", uselist=False)
    contracts: Mapped[list["Contract"]] = relationship(back_populates="project", foreign_keys="Contract.project_id")
    post_shoot_feedbacks: Mapped[list["PostShootFeedback"]] = relationship(back_populates="project")

    @property
    def crew_employee_ids(self) -> list[int]:
        return [e.id for e in self.crew]
