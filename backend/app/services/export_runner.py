"""A galéria-export tényleges végrehajtása (a worker hívja).

Memóriahasználat: a forrás és a cél is **streamelt**. Egy futó job csúcs-
memóriája nagyjából ``EXPORT_CHUNK_BYTES`` (olvasási darab) + a cél backend
puffere (lokálisnál ~1 MiB, S3-nál ``EXPORT_S3_MULTIPART_PART_BYTES``) + a
tervezett bejegyzéslista. Egyetlen fájl vagy a teljes galéria **soha** nem kerül
a memóriába, a méretüktől függetlenül.
"""

from __future__ import annotations

import logging
import time
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.gallery_export import ExportErrorCode, ExportStatus, GalleryExportJob
from app.models.project import Project
from app.services.gallery_export import (
    GalleryExportError,
    GalleryFile,
    plan_gallery,
    record_timeline,
    ttl_expiry,
    utcnow,
)
from app.services.storage import ObjectNotFound, ObjectStorage, StorageError
from app.services.zip64 import (
    ArchiveIntegrityError,
    PlannedEntry,
    Zip64Writer,
    ZipWriteMode,
)

logger = logging.getLogger(__name__)


class ExportFailure(Exception):
    """Az export elbukott; a ``code`` dönti el, hogy újrapróbálható-e."""

    def __init__(self, code: ExportErrorCode, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(slots=True)
class ExportOutcome:
    object_key: str
    size: int
    etag: str
    sha256: str
    files: int
    duration_seconds: float


def _zip_mode() -> ZipWriteMode:
    return (
        ZipWriteMode.DATA_DESCRIPTOR
        if settings.export_zip_streaming_mode
        else ZipWriteMode.CRC_IN_HEADER
    )


class _ProgressReporter:
    """Ritkított haladás-mentés + bérlet-megújítás (heartbeat).

    Nem minden darabnál ír adatbázist: alapból ``EXPORT_PROGRESS_INTERVAL_SECONDS``
    másodpercenként egyszer.
    """

    def __init__(self, db: Session, job: GalleryExportJob, *, interval: float) -> None:
        self._db = db
        self._job = job
        self._interval = interval
        self._bytes = 0
        self._files = 0
        self._last_flush = 0.0

    def add_bytes(self, count: int) -> None:
        self._bytes += count
        now = time.monotonic()
        if now - self._last_flush >= self._interval:
            self._last_flush = now
            self.flush()

    def finish_file(self) -> None:
        self._files += 1

    def flush(self) -> None:
        self._job.bytes_done = self._bytes
        self._job.files_done = self._files
        self._job.lease_expires_at = utcnow() + timedelta(seconds=settings.export_lease_seconds)
        self._db.commit()


def run_export_job(
    db: Session,
    job: GalleryExportJob,
    storage: ObjectStorage,
    *,
    chunk_size: int | None = None,
) -> ExportOutcome:
    """Egy job végigvitele. Sikertelenség esetén ``ExportFailure``-t dob.

    A függvény **nem** állítja a job státuszát ``ready``-re; azt a hívó
    (``app.worker``) teszi, miután a visszaadott eredményt elmentette.
    """
    chunk_size = chunk_size or settings.export_chunk_bytes
    started = time.monotonic()
    project = db.get(Project, job.project_id)
    if project is None:
        raise ExportFailure(ExportErrorCode.SOURCE_MISSING, "A projekt időközben megszűnt.")

    try:
        plan = plan_gallery(db, project, storage=storage)
    except GalleryExportError as exc:
        raise ExportFailure(ExportErrorCode(exc.code) if exc.code in set(ExportErrorCode) else ExportErrorCode.UNKNOWN,
                            exc.message) from exc

    if plan.fingerprint != job.source_fingerprint:
        raise ExportFailure(
            ExportErrorCode.SOURCE_CHANGED,
            "A galéria a csomagolás indítása előtt megváltozott; új exportot kell kérni.",
        )

    # A terv adatai frissülhettek (pl. size_bytes önjavítás).
    job.file_count = plan.file_count
    job.total_source_bytes = plan.total_source_bytes
    job.expected_archive_bytes = plan.expected_archive_bytes
    job.bytes_done = 0
    job.files_done = 0
    db.commit()

    progress = _ProgressReporter(db, job, interval=settings.export_progress_interval_seconds)
    mode = _zip_mode()
    object_key = job.object_key or ""
    if not object_key.startswith(settings.export_object_prefix):
        raise ExportFailure(ExportErrorCode.STORAGE_ERROR, f"Érvénytelen export-kulcs: {object_key!r}")

    try:
        with storage.open_write(object_key, content_type="application/zip") as sink:
            writer = Zip64Writer(sink, mode=mode, on_progress=progress.add_bytes)
            for gallery_file in plan.files:
                _verify_source(storage, gallery_file)
                crc = (
                    _precompute_crc(storage, gallery_file, chunk_size)
                    if mode is ZipWriteMode.CRC_IN_HEADER
                    else None
                )
                writer.add_stream(
                    PlannedEntry(gallery_file.arcname, gallery_file.size, gallery_file.modified),
                    _read_source(storage, gallery_file, chunk_size),
                    crc32=crc,
                )
                progress.finish_file()
            writer.close()
        result = sink.result
    except ArchiveIntegrityError as exc:
        _safe_delete(storage, object_key)
        raise ExportFailure(ExportErrorCode.SOURCE_CHANGED, str(exc)) from exc
    except ObjectNotFound as exc:
        _safe_delete(storage, object_key)
        raise ExportFailure(ExportErrorCode.SOURCE_MISSING, str(exc)) from exc
    except ExportFailure:
        _safe_delete(storage, object_key)
        raise
    except StorageError as exc:
        _safe_delete(storage, object_key)
        raise ExportFailure(ExportErrorCode.STORAGE_ERROR, str(exc), retryable=True) from exc
    except Exception as exc:
        _safe_delete(storage, object_key)
        raise ExportFailure(ExportErrorCode.UNKNOWN, repr(exc), retryable=True) from exc

    # --- ellenőrzés: a kiírt bájtszám pontosan a megtervezett legyen -------
    if result.size != plan.expected_archive_bytes:
        _safe_delete(storage, object_key)
        raise ExportFailure(
            ExportErrorCode.SOURCE_CHANGED,
            f"Az archívum mérete nem a várt: {result.size} != {plan.expected_archive_bytes}.",
        )

    # --- ellenőrzés: a forrás a csomagolás alatt sem változhatott meg -----
    db.expire_all()
    recheck_project = db.get(Project, job.project_id)
    try:
        recheck = plan_gallery(db, recheck_project, storage=storage)
    except GalleryExportError as exc:
        _safe_delete(storage, object_key)
        raise ExportFailure(ExportErrorCode.SOURCE_CHANGED, exc.message) from exc
    if recheck.fingerprint != job.source_fingerprint:
        _safe_delete(storage, object_key)
        raise ExportFailure(
            ExportErrorCode.SOURCE_CHANGED,
            "A galéria csomagolás közben megváltozott; a csomag eldobva, új export kell.",
        )

    progress.flush()
    return ExportOutcome(
        object_key=object_key,
        size=result.size,
        etag=result.etag,
        sha256=result.sha256,
        files=plan.file_count,
        duration_seconds=time.monotonic() - started,
    )


def _verify_source(storage: ObjectStorage, gallery_file: GalleryFile) -> None:
    """Létezik-e a forrás, és pontosan akkora-e, amekkorára terveztünk."""
    try:
        stored = storage.stat(gallery_file.storage_key)
    except ObjectNotFound as exc:
        raise ExportFailure(
            ExportErrorCode.SOURCE_MISSING,
            f"A forrásfájl hiányzik a tárból: {gallery_file.storage_key}",
        ) from exc
    if stored.size != gallery_file.size:
        raise ExportFailure(
            ExportErrorCode.SOURCE_CHANGED,
            f"A forrásfájl mérete megváltozott: {gallery_file.storage_key} "
            f"({gallery_file.size} -> {stored.size} bájt)",
        )


def _read_source(storage: ObjectStorage, gallery_file: GalleryFile, chunk_size: int) -> Iterator[bytes]:
    return storage.read_stream(gallery_file.storage_key, chunk_size=chunk_size)


def _precompute_crc(storage: ObjectStorage, gallery_file: GalleryFile, chunk_size: int) -> int:
    """CRC_IN_HEADER módhoz: a forrás első (extra) olvasása CRC-ért."""
    crc = 0
    seen = 0
    for chunk in storage.read_stream(gallery_file.storage_key, chunk_size=chunk_size):
        crc = zlib.crc32(chunk, crc)
        seen += len(chunk)
    if seen != gallery_file.size:
        raise ExportFailure(
            ExportErrorCode.SOURCE_CHANGED,
            f"A forrásfájl mérete megváltozott CRC-számítás közben: {gallery_file.storage_key}",
        )
    return crc


def _safe_delete(storage: ObjectStorage, key: str) -> None:
    """Részleges/eldobott export törlése.

    **Biztonsági korlát:** csak az export-prefix alatti kulcs törölhető, így a
    takarítás soha nem érintheti az eredeti média-objektumokat.
    """
    if not key or not key.startswith(settings.export_object_prefix):
        logger.error("Törlés megtagadva, a kulcs nem export-prefixű: %r", key)
        return
    try:
        storage.delete(key)
    except Exception:
        logger.warning("Nem sikerült törölni a részleges exportot: %s", key, exc_info=True)


def finalize_ready(db: Session, job: GalleryExportJob, outcome: ExportOutcome) -> None:
    """A job sikeres lezárása (kész állapot, TTL, timeline)."""
    now = utcnow()
    job.status = ExportStatus.READY
    job.object_size = outcome.size
    job.object_etag = outcome.etag
    job.archive_sha256 = outcome.sha256
    job.bytes_done = job.total_source_bytes
    job.files_done = outcome.files
    job.ready_at = now
    job.finished_at = now
    job.expires_at = ttl_expiry(now)
    job.worker_id = None
    job.lease_expires_at = None
    job.error_code = None
    job.error_message = None
    record_timeline(
        db,
        job,
        "GalleryExportReady",
        {
            "project_id": job.project_id,
            "public_id": job.public_id,
            "files": outcome.files,
            "archive_bytes": outcome.size,
            "sha256": outcome.sha256,
            "duration_seconds": round(outcome.duration_seconds, 3),
        },
    )
    db.commit()
