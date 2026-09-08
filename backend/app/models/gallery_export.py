"""Galéria-export job: tartós háttérfeladat egy projekt média-galériájának
ZIP64 csomagolására.

A job **az adatbázisban** él, nem a böngésző memóriájában: az oldal bezárása és
újranyitása után is lekérdezhető, a worker újraindítása után is folytatható.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.types import TZDateTime

if TYPE_CHECKING:
    from app.models.project import Project


class ExportStatus(StrEnum):
    """A UI öt állapota."""

    QUEUED = "queued"      # várakozó
    RUNNING = "running"    # készülő
    READY = "ready"        # kész
    FAILED = "failed"      # hibás
    EXPIRED = "expired"    # lejárt


class ExportErrorCode(StrEnum):
    """Hibakódok - a UI emberi üzenetet mutat rá, a log géppel szűrhető."""

    SOURCE_MISSING = "source_missing"
    SOURCE_CHANGED = "source_changed"
    STORAGE_ERROR = "storage_error"
    STALE_TIMEOUT = "stale_timeout"
    EMPTY_GALLERY = "empty_gallery"
    TOO_MANY_FILES = "too_many_files"
    UNKNOWN = "unknown"


class GalleryExportJob(TimestampMixin, Base):
    """Egy galéria-verzió egyetlen ZIP64 csomagja."""

    __tablename__ = "gallery_export_jobs"
    __table_args__ = (
        # Idempotens létrehozás: egy projekt + egy galéria-verzió = egy job.
        UniqueConstraint("project_id", "source_fingerprint", name="uq_export_project_fingerprint"),
        Index("ix_gallery_export_jobs_status_next", "status", "next_attempt_at"),
        Index("ix_gallery_export_jobs_client", "client_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Kifelé mutatott, kitalálhatatlan azonosító (a numerikus id nem szivárog).
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    #: Denormalizált bérlő-kulcs (Client). Minden lekérdezés ezzel is szűr, hogy a
    #: jogosultság ne függjön több JOIN helyes megírásától.
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    #: A galéria tartalmi ujjlenyomata (sha256). Változó galéria = új ujjlenyomat = új export.
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="gallery_export_status",
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ExportStatus.QUEUED,
        index=True,
    )

    # --- terv / haladás ---
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_source_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    expected_archive_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_done: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    files_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- eredmény ---
    object_key: Mapped[str | None] = mapped_column(String(500))
    object_size: Mapped[int | None] = mapped_column(BigInteger)
    object_etag: Mapped[str | None] = mapped_column(String(128))
    archive_sha256: Mapped[str | None] = mapped_column(String(64))
    filename: Mapped[str | None] = mapped_column(String(255))

    # --- futtatás / megbízhatóság ---
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    worker_id: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    next_attempt_at: Mapped[datetime | None] = mapped_column(TZDateTime())

    started_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    ready_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    #: A kész csomag lejárata (TTL, alapból 48 óra). Utána a csomag törölhető.
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime(), index=True)

    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    project: Mapped["Project"] = relationship()

    # --- származtatott mezők a UI-nak ---

    @property
    def progress_percent(self) -> float:
        if self.status is ExportStatus.READY:
            return 100.0
        if not self.total_source_bytes:
            return 0.0
        return round(min(self.bytes_done / self.total_source_bytes, 1.0) * 100, 2)

    @property
    def is_terminal(self) -> bool:
        return self.status in (ExportStatus.READY, ExportStatus.FAILED, ExportStatus.EXPIRED)
