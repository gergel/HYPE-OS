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

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
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
    gdoc_output_folder_id: str = ""
    google_docs_oauth_token_json: str = ""
    drive_folder_id: str = ""

    @property
    def hype_cc_list(self) -> list[str]:
        return [addr.strip() for addr in self.hype_cc.replace(";", ",").split(",") if addr.strip()]


settings = Settings()
