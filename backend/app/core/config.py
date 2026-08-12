from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg://hype:hype@localhost:5432/hype_os"
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        """Railway (és a legtöbb PaaS) sima 'postgres://'/'postgresql://' URL-t ad -
        ezt írjuk át a psycopg3 driverre, hogy ne kelljen kézzel bütykölni az env var-t."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    secret_key: str = "change-me-to-a-random-secret"
    # 30 nap: a napi/heti munkához nem életszerű, hogy 24 óránként újra be
    # kelljen jelentkezni. A munkamenet emellett GÖRDÜLŐ is: minden oldal-
    # betöltésnél megújul, ha már a felénél jár (lásd frontend middleware.ts
    # + POST /auth/refresh), tehát aki használja a rendszert, sosem fut ki.
    access_token_expire_minutes: int = 60 * 24 * 30
    algorithm: str = "HS256"

    #: A VÉDETT RENDSZERGAZDA fiók(ok) e-mail címe, vesszővel elválasztva.
    #:
    #: Ez a fiók sosem eshet ki a rendszerből: nem lehet inaktívvá tenni, nem
    #: veszítheti el az admin szerepkörét, és nem lehet neki oldal- vagy
    #: mező-korlátozást beállítani (lásd core/security.vedett_rendszergazda).
    #:
    #: Miért kell? Mert a jogosultságokat ugyanazon a felületen állítjuk, amit
    #: azok védenek - egyetlen félrekattintás (inaktívra állítás, szerepkör
    #: átírása, "hozzáférés visszavonása") ki tudja zárni azt az embert, aki
    #: egyedül tudná visszaadni a jogot. Adatbázis-hozzáférés nélkül ez
    #: kívülről nem javítható, tehát kell egy fiók, amit a rendszer maga tart
    #: életben.
    #:
    #: Beállításként (env változó) és nem a kódba égetve, hogy tulajdonosváltás
    #: vagy címcsere ne igényeljen kódmódosítást és új deployt.
    vedett_admin_emailek: str = "vidor.gergely@gmail.com"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "hype-os-storage"
    r2_public_url: str = ""

    # Alapértelmezetten minden origin engedélyezett - az API kizárólag Bearer
    # token-nel (Authorization header, nem cookie-val) hitelesít, ezért nincs
    # CSRF-kockázat a wildcard origin engedélyezésénél. Ez azért fontos, mert a
    # korábbi szigorúbb alapérték (csak http://localhost:3000) éles Railway
    # deploy-on néma hálózati hibát okozott minden írási műveletnél (a böngésző
    # blokkolta a frontend<->backend hívást, mert a frontend domain-je nem volt
    # rajta a listán) - ha mégis szűkíteni akarod, add meg vesszővel elválasztva.
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # ───────── Diszpó/szerződés küldés (Gmail + Google Docs/Drive) ─────────
    # Mind opcionális - hitelesítő adatok nélkül a diszpó/szerződés küldő
    # végpontok egyértelmű hibát adnak vissza, de az app egyébként elindul.
    gmail_sender: str = ""
    gmail_sender_name: str = ""
    # A diszpó-levelek (előzetes, teljes, utókövető kérdőív) feladóneve - ez
    # látszik a címzett postaládájában a cím helyett. Külön a generikus
    # GMAIL_SENDER_NAME-től, mert a szerződés/TIG levelek nem a gyártástól
    # mennek. A küldő CÍM mindig GMAIL_SENDER marad.
    dispo_sender_name: str = "HYPE GYÁRTÁS"
    gmail_oauth_token_json: str = ""
    gmail_oauth_client_id: str = ""
    gmail_oauth_client_secret: str = ""
    gmail_oauth_refresh_token: str = ""
    gmail_service_account_json: str = ""
    gmail_impersonate_user: str = ""
    hype_cc: str = ""

    gdoc_dispo_template_id: str = ""
    gdoc_contract_template_id: str = ""
    gdoc_alvallalkozoi_szerzodes_template_id: str = ""
    # Az ÁLLÓ (alvállalkozói) keretszerződés Google Docs sablonja - a csatolt
    # "alvallalkozo-keret" Railway program GOOGLE_DRIVE_TEMPLATE_ID-je. Külön
    # sablon, mint az eseti szerződésé: más a szövege és más mezőket vár.
    gdoc_keretszerzodes_template_id: str = ""
    # Hova kerüljön a kész keretszerződés (Docs + PDF). ÜRESEN HAGYVA a sablon
    # SAJÁT mappájába megy - ezt kérte a felhasználó, és így nem kell külön
    # mappát karbantartani. Csak akkor töltsd ki, ha máshova akarod irányítani.
    gdoc_keretszerzodes_folder_id: str = ""
    # A MEGRENDELŐI papírok sablonjai (a csatolt Notion-programok
    # GOOGLE_DRIVE_TEMPLATE_ID-jai) - a placeholder-nevek egyeznek, tehát a
    # meglévő sablonok változtatás nélkül használhatók.
    gdoc_megrendeloi_eseti_template_id: str = ""
    gdoc_megrendeloi_tig_template_id: str = ""
    gdoc_megrendeloi_keret_template_id: str = ""
    # A megrendelői keretszerződéshez tartozó SZERZŐDÉSMÓDOSÍTÁS sablonja.
    # Alapértéknek a felhasználó által megadott dokumentum van beírva, hogy
    # beállítás nélkül is működjön - env-ből felülírható, ha új sablon kell.
    # Placeholderek: {{nev}} {{hely}} {{nyilvszam}} {{adoszam}} {{kepvis}}.
    gdoc_keret_modositas_template_id: str = "1EcuVGgyUvazBFDzFmDSYUfcioQWFH6-tvLmSDh5ASNY"
    # Hova kerüljön a kész módosítás-PDF. Üresen a keretszerződések mappája,
    # majd a generikus kimeneti mappa, végül a SABLON SAJÁT mappája a cél -
    # így nincs külön karbantartandó beállítás (lásd a route-ot).
    gdoc_keret_modositas_folder_id: str = ""
    # A szerződésmódosítás levele MÁS címről megy, mint a többi papír: a
    # felhasználó kérése szerint az admin fiókból, annak a Gmailben beállított
    # aláírásával. A cím legyen a küldő fiók saját címe vagy annak felvett
    # álneve (send-as alias), különben a Gmail elutasítja a levelet.
    modositas_sender: str = "admin@hypest.hu"
    gdoc_kulsos_tig_template_id: str = ""
    gdoc_belsos_tig_template_id: str = ""
    gdoc_output_folder_id: str = ""
    google_docs_oauth_token_json: str = ""
    drive_folder_id: str = ""
    # A Külsős TIG saját, kész-fájl célmappája - ha be van állítva, ez élvez
    # elsőbbséget a generikus gdoc_output_folder_id/drive_folder_id felett
    # (lásd api/routes/performance_certificates.py generate_and_send).
    drive_kulsos_tig: str = ""
    # Ugyanez a Belsős TIG-hez (lásd api/routes/internal_performance_certificates.py).
    drive_belsos_tig: str = ""
    # A kiküldött diszpók kész PDF-jének célmappája (lásd services/dispo.py
    # send_diszpo) - ha üres, a generikus gdoc_output_folder_id/drive_folder_id
    # a cél, és ha az sincs, a Drive gyökere.
    drive_diszpo_folder_id: str = ""

    # A különálló belsős-TIG program (belsos-TIG-main) env-nevei. Azért
    # fogadjuk el őket, hogy a HYPE OS ugyanazzal a Railway beállítással
    # működjön, amivel az a program eddig futott - ne kelljen ugyanazt a
    # sablont/mappát/tokent új néven még egyszer felvenni.
    google_drive_template_id: str = ""
    notion_file_folder_id: str = ""
    tigtoken_json: str = ""

    @property
    def keretszerzodes_template_id(self) -> str:
        """A keretszerződés sablonja. A csatolt program a GOOGLE_DRIVE_TEMPLATE_ID
        alatt tartotta - de azt a belsős TIG is használja, ezért csak akkor
        esünk vissza rá, ha saját sablon nincs megadva."""
        return self.gdoc_keretszerzodes_template_id

    @property
    def belsos_tig_template_id(self) -> str:
        return self.gdoc_belsos_tig_template_id or self.google_drive_template_id

    @property
    def belsos_tig_folder_id(self) -> str:
        return (
            self.drive_belsos_tig
            or self.notion_file_folder_id
            or self.gdoc_output_folder_id
            or self.drive_folder_id
        )

    @property
    def diszpo_folder_id(self) -> str:
        return self.drive_diszpo_folder_id or self.gdoc_output_folder_id or self.drive_folder_id

    @property
    def hype_cc_list(self) -> list[str]:
        return [addr.strip() for addr in self.hype_cc.replace(";", ",").split(",") if addr.strip()]

    # ───────── Naptár szinkron (Google Calendar -> Project, percenkénti) ─────────
    # KÜLÖN Google fiók, mint a fenti Gmail/Docs - a felhasználó megerősítette,
    # hogy a HYPE CALENDAR más fióknál van, ezért saját hitelesítő adatok kellenek
    # (ugyanaz a kettős minta, mint fent: OAuth token JSON VAGY service account
    # JSON + opcionális impersonation - lásd services/google_calendar.py). Ha egyik
    # sincs beállítva, a percenkénti sync feladat csendben kihagyja a futást.
    google_calendar_oauth_token_json: str = ""
    google_calendar_service_account_json: str = ""
    google_calendar_impersonate_user: str = ""
    # Ha üres, a szinkron a naptárak listájából NÉV szerint (google_calendar_name)
    # keresi meg a naptárat - ha ismert a naptár ID-je (pl. xxx@group.calendar.google.com),
    # ezzel megspórolható a névkeresés és egyértelműsíthető azonos nevű naptárak esetén.
    google_calendar_id: str = ""
    google_calendar_name: str = "HYPE CALENDAR"
    # Melyik naptár-esemény szín jelent meetinget/helyszínbejárást (nem
    # diszponálandó) - Google colorId-k vesszővel elválasztva. Alapból csak a
    # "3" (Szőlő - a Google palettájának lila árnyalata). Lásd
    # services/google_calendar.py NAPTAR_SZINEK.
    naptar_meeting_szinek: str = "3"

    # A "csak jelentkezz be egyszer" folyamathoz (lásd services/google_oauth.py):
    # ezekkel a HYPE OS a saját nevében kéri el a naptár olvasási jogot, a kapott
    # refresh tokent pedig ADATBÁZISBAN tárolja - így adminnak soha nem kell
    # kézzel token/service account JSON-t másolgatnia környezeti változóba.
    # Ha nincs külön naptár-kliens megadva, a már meglévő Gmail OAuth kliensre
    # esünk vissza (ugyanabban a Google Cloud projektben lévő OAuth client
    # több scope-ra is használható), hogy ne kelljen új klienst regisztrálni.
    google_calendar_oauth_client_id: str = ""
    google_calendar_oauth_client_secret: str = ""

    @property
    def calendar_oauth_client_id(self) -> str:
        return self.google_calendar_oauth_client_id or self.gmail_oauth_client_id

    @property
    def calendar_oauth_client_secret(self) -> str:
        return self.google_calendar_oauth_client_secret or self.gmail_oauth_client_secret

    # ───────── AI Assistant (Google Gemini, function calling) ─────────
    # gemini_api_key hiányában az /ai-assistant/ask végpont egyértelmű
    # hibaüzenetet ad vissza, de az app egyébként elindul. Flash az
    # alapértelmezett: ez egy belső, kis léptékű céges eszköz, ahol a gyors
    # válasz többet ér, mint a nagyobb modell - GEMINI_MODEL-lel átállítható
    # (pl. "gemini-2.5-pro").
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ───────── Média Portál (ügyfél videó/kép átadó felület, /p/{slug}) ─────────
    # A Hype-repo-main (különálló client-portál projekt) 1:1 portolt funkciója -
    # mind opcionális, hiányukban az adott képesség (fizetés/Notion sync) csak
    # egyértelmű hibát ad, a portál videó/kép átadás alapfunkciója attól még megy.
    frontend_base_url: str = ""
    api_base_url: str = ""

    # A publikus portál SAJÁT domainje (hypeclient.com) - ez megy ki az
    # ügyfeleknek, míg a HYPE OS admin felület a frontend_base_url-en marad.
    # Minden ügyfél felé menő link (megosztó link, fizetés utáni
    # visszairányítás) ezt használja. Üresen hagyva a frontend_base_url-ra esik
    # vissza, tehát egydomaines telepítésnél nincs teendő.
    portal_base_url: str = ""

    @property
    def portal_front_base(self) -> str:
        return (self.portal_base_url or self.frontend_base_url).rstrip("/")

    barion_pos_key: str = ""
    barion_env: str = "test"  # test | prod
    barion_payee: str = ""

    @property
    def barion_api_base(self) -> str:
        return "https://api.test.barion.com" if self.barion_env == "test" else "https://api.barion.com"

    # A Számlázz.hu Számla Agent kulcsa: ebből állítjuk ki a számlát a portálon
    # keresztül fizetett tárhely-hosszabbításról (lásd services/portal_szamlazz.py).
    # Üresen hagyva a fizetés ugyanúgy működik, csak számla nem készül.
    szamlazz_agent_key: str = ""

    # Külön Notion adatbázis a portál-projektekhez (NEM ugyanaz, mint a fő
    # HYPE OS Notion importja) - opcionális "Notion szinkron" admin gombhoz.
    portal_notion_api_key: str = ""
    portal_notion_database_id: str = ""


settings = Settings()
