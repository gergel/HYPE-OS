from datetime import datetime

from pydantic import BaseModel, Field

from app.models.gallery_export import ExportStatus


class GalleryExportRead(BaseModel):
    """A UI ebből rajzolja az öt állapotot és a valós előrehaladást."""

    public_id: str
    project_id: int
    status: ExportStatus
    source_fingerprint: str

    file_count: int
    files_done: int
    total_source_bytes: int
    expected_archive_bytes: int
    bytes_done: int
    progress_percent: float

    filename: str | None = None
    object_size: int | None = None
    object_etag: str | None = None
    archive_sha256: str | None = None

    attempts: int
    max_attempts: int
    error_code: str | None = None
    error_message: str | None = None

    created_at: datetime
    started_at: datetime | None = None
    ready_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class GalleryPlanRead(BaseModel):
    """A galéria aktuális verziója - a UI ebből tudja, mekkora csomag készülne."""

    project_id: int
    source_fingerprint: str
    file_count: int
    total_source_bytes: int
    expected_archive_bytes: int


class GalleryExportStateRead(BaseModel):
    """Az oldal újranyitásakor lekért teljes állapot."""

    plan: GalleryPlanRead | None = None
    job: GalleryExportRead | None = None
    #: Üzleti hiba, ami miatt most nem lehet exportot indítani (pl. üres galéria).
    unavailable_reason: str | None = None


class DownloadTicketRead(BaseModel):
    """Kiadott, jogosultság-ellenőrzött letöltési URL.

    A link lejár, de **ugyanarra a változatlan objektumra** mutat: megújítás után
    a félbeszakadt letöltés HTTP Range-dzsel folytatható.
    """

    url: str
    expires_at: datetime
    filename: str
    size: int = Field(description="A csomag pontos mérete bájtban (Content-Length).")
    etag: str
    sha256: str | None = None
    direct: bool = Field(description="Igaz, ha az URL közvetlenül az objektumtárra mutat (presigned).")
