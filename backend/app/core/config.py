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
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

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
    gdoc_output_folder_id: str = ""
    google_docs_oauth_token_json: str = ""
    drive_folder_id: str = ""

    @property
    def hype_cc_list(self) -> list[str]:
        return [addr.strip() for addr in self.hype_cc.replace(";", ",").split(",") if addr.strip()]

    # ───────── AI Assistant (Anthropic Claude, tool-calling) ─────────
    # anthropic_api_key hiányában az /ai-assistant/ask végpont egyértelmű
    # hibaüzenetet ad vissza, de az app egyébként elindul. Sonnet 5-öt
    # használunk alapértelmezettként (nem Opus-t) - ez egy belső, viszonylag
    # kis léptékű céges eszköz, ahol a Sonnet ár/érték aránya jobban megéri.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # ───────── Média Portál (ügyfél videó/kép átadó felület, /p/{slug}) ─────────
    # A Hype-repo-main (különálló client-portál projekt) 1:1 portolt funkciója -
    # mind opcionális, hiányukban az adott képesség (fizetés/Notion sync) csak
    # egyértelmű hibát ad, a portál videó/kép átadás alapfunkciója attól még megy.
    frontend_base_url: str = ""
    api_base_url: str = ""

    barion_pos_key: str = ""
    barion_env: str = "test"  # test | prod
    barion_payee: str = ""

    @property
    def barion_api_base(self) -> str:
        return "https://api.test.barion.com" if self.barion_env == "test" else "https://api.barion.com"

    # Külön Notion adatbázis a portál-projektekhez (NEM ugyanaz, mint a fő
    # HYPE OS Notion importja) - opcionális "Notion szinkron" admin gombhoz.
    portal_notion_api_key: str = ""
    portal_notion_database_id: str = ""


settings = Settings()
