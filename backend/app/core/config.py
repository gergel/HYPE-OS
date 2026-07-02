from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg://hype:hype@localhost:5432/hype_os"
    redis_url: str = "redis://localhost:6379/0"

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


settings = Settings()
