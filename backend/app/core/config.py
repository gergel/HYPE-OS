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
    r2_endpoint_url: str = ""
    r2_region: str = "auto"

    cors_origins: str = "http://localhost:3000"

    # --- Storage backend (Storage modul + galéria-export) ---
    # "local" = privát fájlrendszer (fejlesztés/teszt, nem publikus könyvtár),
    # "s3"    = Cloudflare R2 / bármely S3-kompatibilis privát bucket.
    storage_backend: str = "local"
    local_storage_root: str = "./var/storage"
    #: Az eredeti (forrás) média objektumok kulcs-prefixe. A takarítás soha nem nyúl ide.
    media_object_prefix: str = "media/"

    # --- Galéria ZIP64 export ---
    #: A kész exportok kulcs-prefixe a privát objektumtárban. A törlés CSAK ezen belül engedett.
    export_object_prefix: str = "exports/"
    #: Ideiglenes csomagok élettartama órában (alapértelmezés: 48 óra).
    export_ttl_hours: int = 48
    #: A kiadott letöltési URL érvényessége másodpercben (megújítható, ugyanarra az objektumra).
    export_download_url_ttl_seconds: int = 900
    #: Egy worker-processzen belüli párhuzamos export-feladatok maximuma.
    export_worker_concurrency: int = 2
    #: Egy job hányszor próbálkozhat összesen, mielőtt véglegesen hibás lesz.
    export_max_attempts: int = 3
    #: A futó job bérletének hossza; ennél régebbi heartbeat = stale job (újra sorba kerül).
    export_lease_seconds: int = 120
    #: Streamelési darabméret byte-ban (a worker memóriahasználatának felső korlátja/szál).
    export_chunk_bytes: int = 8 * 1024 * 1024
    #: S3/R2 multipart feltöltés részméret byte-ban (min. 5 MiB az S3 API szerint).
    export_s3_multipart_part_bytes: int = 64 * 1024 * 1024
    #: Worker ciklus alvásideje, ha nincs feladat.
    export_worker_poll_seconds: float = 2.0
    #: Progress/heartbeat mentés gyakorisága másodpercben (nem minden chunknál írunk DB-t).
    export_progress_interval_seconds: float = 2.0
    #: Egy galéria-exportba bevonható fájlok maximuma (védelem a memóriában tartott
    #: központi könyvtár ellen; 0 = nincs korlát).
    export_max_files: int = 200_000
    #: Ha igaz, minden bejegyzés data descriptorral íródik (egy menetes, seek nélküli írás).
    #: Ha hamis, a worker fájlonként előre kiszámolja a CRC32-t (kétszeres olvasás), és a
    #: CRC a lokális fejlécbe kerül - csak akkor kell, ha egy legacy kliens nem tud
    #: data descriptort olvasni.
    export_zip_streaming_mode: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def s3_endpoint_url(self) -> str:
        """R2 endpoint: explicit R2_ENDPOINT_URL, vagy az account_id-ből képzett R2 URL."""
        if self.r2_endpoint_url:
            return self.r2_endpoint_url
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return ""


settings = Settings()
