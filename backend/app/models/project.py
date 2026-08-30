from datetime import date, datetime, time

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Table, Text, Time
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

    #: Melyik Project Code alá tartozik. ÜRES is lehet: a naptárból érkező
    #: forgatásnak még nincs kódja, és amíg nincs, nem söpörjük gyűjtő kód alá
    #: sem - egy gyűjtőbe rakott projekt ugyanis úgy néz ki, mintha el lenne
    #: intézve (lásd services/projektkod_kotes.py).
    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    forgatas_datuma: Mapped[date | None] = mapped_column(Date)
    forgatas_datuma_vege: Mapped[date | None] = mapped_column(
        Date, comment="A Notion 'Date' property end-je - több napos forgatás záró napja, ha van"
    )
    # A forgatás napon belüli időpontja (hánytól hányig). Külön oszlopban, nem
    # a dátumba olvasztva, mert a forgatás dátuma önmagában is értelmes és
    # használt adat (naptár nézet, diszpó tárgya, TIG teljesítési idő), az
    # időpont pedig gyakran csak később derül ki. A HYPE CALENDAR-ból
    # szinkronizálva is töltjük, ha az esemény nem egész napos
    # (lásd services/google_calendar.py _parse_event_dates).
    forgatas_kezdes_ido: Mapped[time | None] = mapped_column(Time, comment="Forgatás kezdete (óra:perc)")
    forgatas_veg_ido: Mapped[time | None] = mapped_column(Time, comment="Forgatás vége (óra:perc)")
    #: KÉZI DÁTUM-ZÁR: igaz, ha a forgatás dátumait (a fenti négy mezőt) a HYPE
    #: OS felületén, kézzel állították be (lásd routes/projects.py
    #: _datum_zar_kezelese). Amíg igaz, SEM a percenkénti naptár-szinkron
    #: (services/google_calendar.py), SEM a Notion-import
    #: (notion_import/importers_wave2.py) nem nyúlhat a dátumokhoz - a
    #: felhasználó explicit kérése: amit kézzel beállít (pl. egy záró dátumot),
    #: azt semmilyen automatizmus ne törölhesse/írhassa át. A zárat a kezdő
    #: dátum kézi TÖRLÉSE oldja fel (= "visszaadom a szinkronnak").
    forgatas_datum_kezzel_beallitva: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="Forgatás dátumai kézzel beállítva (szinkron nem írhatja felül)"
    )
    helyszin: Mapped[str | None] = mapped_column(String(255))
    allapot: Mapped[str | None] = mapped_column(String(50))
    google_calendar_event_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        comment="A HYPE CALENDAR naptárból szinkronizált esemény Google Calendar event ID-je - "
        "csak a naptárból automatikusan létrehozott projekteknek van (lásd services/google_calendar.py).",
    )
    # A naptáresemény színe magyar néven ("Lila", "Zöld"…), ha a naptárban
    # kaptott egyet. Azért tároljuk, mert a "lila = meeting" szabály ezen
    # múlik - enélkül nem lenne látható, MIÉRT lett egy esemény
    # nem-diszponálandó (lásd services/google_calendar.py MEETING_SZINEK).
    naptar_szin: Mapped[str | None] = mapped_column(String(30), comment="Naptár szín")
    # Nem forgatás, hanem meeting / helyszínbejárás - nincs mit diszponálni.
    # A naptár-szinkron a szín alapján állítja be, de kézzel is átállítható:
    # a naptárban elfelejtett szín nem zárhat ki egy valódi forgatást örökre.
    nem_diszponalando: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="Nem diszponálandó (meeting)"
    )
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
    #: Ha ez a projekt egy TÖBB NAPOS forgatásból leválasztott nap (lásd
    #: services/project_actions.create_feldarabolas), akkor itt az eredeti,
    #: "egész" projekt id-je áll. Ebből tudja a rendszer, hogy diszponálni a
    #: LEVÁLASZTOTT napot kell, nem az egészet (lásd dashboard
    #: _tomorrow_dispo_tasks).
    feldarabolas_szulo_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), comment="Melyik projektből lett leválasztva ez a nap"
    )

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

    #: A több napos forgatásból leválasztott napok (lásd feldarabolas_szulo_id).
    feldarabolt_napok: Mapped[list["Project"]] = relationship(
        back_populates="feldarabolas_szulo", foreign_keys=[feldarabolas_szulo_id]
    )
    feldarabolas_szulo: Mapped["Project"] = relationship(
        back_populates="feldarabolt_napok", remote_side="Project.id", foreign_keys=[feldarabolas_szulo_id]
    )

    project_code: Mapped["ProjectCode | None"] = relationship(back_populates="projects")
    campaign: Mapped["Campaign"] = relationship(back_populates="projects")
    crew: Mapped[list["Employee"]] = relationship(secondary=project_crew, back_populates="projects")

    # A projekt "saját" rekordjai: a projekt törlésekor velük együtt törlődnek.
    # Cascade nélkül a SQLAlchemy alapból NULL-ra állítaná a gyerek project_id-
    # jét, ami itt kétféleképp is rossz: a NOT NULL oszlopoknál (assignments,
    # callsheets, post_shoot_feedbacks, performance_certificates) adatbázis-
    # hibával elszállt a törlés, a nullable-öknél pedig némán árván maradt a
    # sor - egy eseti szerződésből például project_id nélkül keretszerződés
    # lett volna (lásd subcontractor_contracts.py _load_contract_lookup).
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    callsheets: Mapped[list["Callsheet"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    contracts: Mapped[list["Contract"]] = relationship(
        back_populates="project", foreign_keys="Contract.project_id", cascade="all, delete-orphan"
    )
    post_shoot_feedbacks: Mapped[list["PostShootFeedback"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    performance_certificates: Mapped[list["PerformanceCertificate"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    #: A rá SZÓLÓ TIG-tételek. Nem ugyanaz, mint a fenti: egy TIG egy projekt
    #: "otthonában" készül, de több forgatás munkáját is igazolhatja - ide
    #: azok a tételek tartoznak, amik erre a napra szólnak, akkor is, ha a
    #: papír máshonnan indult (lásd models/performance_certificate.py).
    tig_tetelek: Mapped[list["PerformanceCertificateTetel"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    #: Kinek a nevére megy a szerződés/TIG az egyes stábtagok munkájáért, ha
    #: nem a sajátjukéra (lásd models/project_szamlazo.py).
    szamlazok: Mapped[list["ProjectSzamlazo"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    # A Média Portál tartalma SZÁNDÉKOSAN nem törlődik a projekttel: ügyfélnek
    # kiadott (akár már kifizetett) anyag, amit nem szabad egy projekt-törlés
    # mellékhatásaként elveszíteni. Ha van ilyen, a törlés érthető hibaüzenettel
    # elutasításra kerül (lásd api/routes/projects.py delete-ellenőrzése).
    media_items: Mapped[list["Media"]] = relationship(back_populates="project")
    folders: Mapped[list["Folder"]] = relationship(back_populates="project")
    portal: Mapped["Portal"] = relationship(back_populates="project", uselist=False)

    #: Alvállalkozói projekt kiadások, amik EHHEZ a forgatáshoz kötik a
    #: bennük megadott embert (lásd models/finance.py
    #: Expense.alvallalkozo_project_id). VIEWONLY: az írás magán a Kiadáson
    #: keresztül történik, nem itt.
    alvallalkozo_kiadasok: Mapped[list["Expense"]] = relationship(
        foreign_keys="Expense.alvallalkozo_project_id", viewonly=True
    )

    @property
    def crew_employee_ids(self) -> list[int]:
        return [e.id for e in self.crew]

    @property
    def alvallalkozo_stab(self) -> list["Employee"]:
        """Azok az emberek, akik NEM stábtagok (tehát a diszpó sosem hívja be
        őket), de egy hozzájuk kötött alvállalkozói projekt kiadás miatt mégis
        kell tőlük szerződés és TIG - lásd Expense.alvallalkozo_project_id és
        api/routes/subcontractor_contracts.szerzodest_igenylo_emberek."""
        return [e.employee for e in self.alvallalkozo_kiadasok if e.employee is not None]
