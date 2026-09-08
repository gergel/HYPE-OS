"""Galéria-export szolgáltatás: verziószámítás, jogosultság, job-életciklus.

Fogalmak
--------
*Galéria*: egy ``Project`` alatt lévő, ``status='ready'`` ``Media`` sorok
(``Folder``-ekbe rendezve). Az eredeti képek/videók a privát objektumtárban
élnek, az adatbázisban csak a ``storage_key`` van.

*Galéria-verzió (ujjlenyomat)*: a galéria tartalmi sha256-ja. Ugyanaz a verzió
= ugyanaz a csomag = kész export újrahasznosítható. Bármi változik (új fájl,
törölt fájl, átnevezés, más méret/hash, más mappa), új ujjlenyomat születik,
tehát **új** exportot kell készíteni.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee, SystemRole
from app.models.gallery_export import ExportErrorCode, ExportStatus, GalleryExportJob
from app.models.media import Folder, Media
from app.models.project import Project
from app.models.timeline import TimelineEvent
from app.models.types import ensure_utc
from app.services.storage import ObjectNotFound, ObjectStorage
from app.services.zip64 import (
    ArcNameAllocator,
    PlannedEntry,
    ZipWriteMode,
    predict_archive_size,
    sanitize_arcpath,
    sanitize_component,
)

#: Belsős szerepkörök: minden projektet látnak.
INTERNAL_ROLES = (SystemRole.ADMIN, SystemRole.OPERATOR, SystemRole.VAGO)
#: Job létrehozására jogosult szerepkörök (az ügyfél a saját galériáját kérheti).
CREATE_ROLES = (SystemRole.ADMIN, SystemRole.OPERATOR, SystemRole.VAGO, SystemRole.UGYFEL)


def utcnow() -> datetime:
    return datetime.now(UTC)


class GalleryExportError(Exception):
    """Üzleti hiba, amit az API 4xx-re fordít."""

    def __init__(self, code: ExportErrorCode | str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message


# --- Terv --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GalleryFile:
    media_id: int
    arcname: str
    storage_key: str
    size: int
    checksum_sha256: str | None
    modified: datetime


@dataclass(slots=True)
class GalleryPlan:
    files: list[GalleryFile] = field(default_factory=list)
    fingerprint: str = ""
    total_source_bytes: int = 0
    expected_archive_bytes: int = 0

    @property
    def file_count(self) -> int:
        return len(self.files)


def _zip_mode() -> ZipWriteMode:
    return (
        ZipWriteMode.DATA_DESCRIPTOR
        if settings.export_zip_streaming_mode
        else ZipWriteMode.CRC_IN_HEADER
    )


def plan_gallery(
    db: Session, project: Project, *, storage: ObjectStorage | None = None
) -> GalleryPlan:
    """A galéria determinisztikus csomagolási terve + tartalmi ujjlenyomata.

    ``storage`` megadásakor a hiányzó ``size_bytes`` mezőket a tárból pótolja és
    el is menti (önjavítás); enélkül a hiányzó méret hibát okoz, mert STORE
    módban a méret nélkül nem tervezhető az archívum.
    """
    folders = {
        folder.id: folder
        for folder in db.scalars(select(Folder).where(Folder.project_id == project.id))
    }
    rows = list(
        db.scalars(
            select(Media)
            .where(Media.project_id == project.id, Media.status == "ready")
        )
    )

    def sort_key(media: Media) -> tuple:
        folder = folders.get(media.folder_id) if media.folder_id else None
        return (
            0 if folder is None else 1,
            folder.sort_order if folder else 0,
            folder.id if folder else 0,
            media.title or "",
            media.id,
        )

    rows.sort(key=sort_key)
    if not rows:
        raise GalleryExportError(
            ExportErrorCode.EMPTY_GALLERY,
            "A galéria nem tartalmaz letölthető (ready) fájlt.",
        )
    if settings.export_max_files and len(rows) > settings.export_max_files:
        raise GalleryExportError(
            ExportErrorCode.TOO_MANY_FILES,
            f"A galéria {len(rows)} fájlt tartalmaz, a korlát {settings.export_max_files}.",
        )

    allocator = ArcNameAllocator()
    files: list[GalleryFile] = []
    digest = hashlib.sha256()
    digest.update(b"hype-os/gallery-export/v1\n")
    digest.update(f"project={project.id}\n".encode())
    digest.update(f"mode={_zip_mode().value}\n".encode())

    dirty = False
    for media in rows:
        size = media.size_bytes
        if size is None:
            if storage is None:
                raise GalleryExportError(
                    ExportErrorCode.SOURCE_MISSING,
                    f"A(z) {media.title!r} médiához nincs ismert méret (size_bytes). "
                    "Futtasd a `python -m app.worker backfill-sizes` parancsot.",
                )
            try:
                size = storage.stat(media.storage_key).size
            except ObjectNotFound as exc:
                raise GalleryExportError(
                    ExportErrorCode.SOURCE_MISSING,
                    f"A forrásfájl nem található a tárban: {media.storage_key}",
                ) from exc
            media.size_bytes = size
            dirty = True

        folder = folders.get(media.folder_id) if media.folder_id else None
        parts = [folder.nev] if folder else []
        parts.append(_display_name(media))
        arcname = allocator.allocate(sanitize_arcpath(parts))
        modified = ensure_utc(media.created_at) or utcnow()
        files.append(
            GalleryFile(
                media_id=media.id,
                arcname=arcname,
                storage_key=media.storage_key,
                size=int(size),
                checksum_sha256=media.checksum_sha256,
                modified=modified,
            )
        )
        digest.update(
            "\x1f".join(
                [
                    str(media.id),
                    media.storage_key,
                    str(size),
                    media.checksum_sha256 or "",
                    arcname,
                    modified.astimezone(UTC).isoformat(timespec="seconds"),
                ]
            ).encode("utf-8")
        )
        digest.update(b"\x1e")

    if dirty:
        db.commit()

    planned = [PlannedEntry(f.arcname, f.size, f.modified) for f in files]
    return GalleryPlan(
        files=files,
        fingerprint=digest.hexdigest(),
        total_source_bytes=sum(f.size for f in files),
        expected_archive_bytes=predict_archive_size(planned, mode=_zip_mode()),
    )


def _display_name(media: Media) -> str:
    """A ZIP-en belüli fájlnév: a ``title``, a storage kulcs kiterjesztésével."""
    title = (media.title or "").strip() or f"media-{media.id}"
    suffix = ""
    tail = media.storage_key.rsplit("/", 1)[-1]
    if "." in tail:
        candidate = tail.rsplit(".", 1)[-1]
        if 1 <= len(candidate) <= 16 and candidate.isalnum():
            suffix = f".{candidate}"
    if suffix and title.lower().endswith(suffix.lower()):
        suffix = ""
    return sanitize_component(f"{title}{suffix}", fallback=f"media-{media.id}")


# --- Jogosultság -------------------------------------------------------------


def tenant_client_id(db: Session, project: Project) -> int:
    """A projekt bérlője (Client) a ProjectCode-on keresztül."""
    return project.project_code.client_id


def get_project_for_user(db: Session, project_id: int, user: Employee) -> Project:
    """Projekt betöltése bérlő-ellenőrzéssel.

    Idegen bérlő esetén **404**, nem 403 - így a projekt létezése sem szivárog.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise GalleryExportError("not_found", "A projekt nem található.")
    if user.role in INTERNAL_ROLES:
        return project
    if user.role is SystemRole.UGYFEL:
        if user.client_id is not None and tenant_client_id(db, project) == user.client_id:
            return project
        raise GalleryExportError("not_found", "A projekt nem található.")
    raise GalleryExportError("forbidden", "Nincs jogosultságod ehhez a projekthez.")


def assert_job_visible(db: Session, job: GalleryExportJob, user: Employee) -> None:
    """Job-hozzáférés ellenőrzése (lekérdezésnél és letöltési link kiadásánál is)."""
    if user.role in INTERNAL_ROLES:
        return
    if user.role is SystemRole.UGYFEL and user.client_id is not None and job.client_id == user.client_id:
        return
    raise GalleryExportError("not_found", "Az export nem található.")


# --- Job életciklus ----------------------------------------------------------


def object_key_for(project_id: int, fingerprint: str) -> str:
    return f"{settings.export_object_prefix}{project_id}/{fingerprint}.zip"


def export_filename(project: Project, fingerprint: str) -> str:
    """Ügyfélbarát, Unicode-biztos fájlnév a letöltéshez."""
    code = getattr(project.project_code, "projektkod", None) or f"projekt-{project.id}"
    stem = f"{code}-{project.nev}".strip("-")
    stem = unicodedata.normalize("NFC", stem)
    stem = re.sub(r"\s+", "-", stem)
    stem = sanitize_component(stem, fallback=f"projekt-{project.id}")
    return f"{stem}-{fingerprint[:8]}.zip"


def ttl_expiry(now: datetime | None = None) -> datetime:
    return (now or utcnow()) + timedelta(hours=settings.export_ttl_hours)


def get_or_create_job(
    db: Session, project: Project, user: Employee, *, storage: ObjectStorage | None = None
) -> tuple[GalleryExportJob, bool]:
    """Idempotens job-létrehozás.

    * kész és még nem járt le -> ugyanazt adja vissza (nincs újracsomagolás),
    * várakozó/futó -> ugyanazt adja vissza (dupla kattintás nem indít másodikat),
    * hibás vagy lejárt -> ugyanaz a sor újraindul (új próbálkozás),
    * más galéria-verzió -> **új** job.
    """
    plan = plan_gallery(db, project, storage=storage)
    client_id = tenant_client_id(db, project)
    now = utcnow()

    existing = db.scalars(
        select(GalleryExportJob).where(
            GalleryExportJob.project_id == project.id,
            GalleryExportJob.source_fingerprint == plan.fingerprint,
        )
    ).first()

    if existing is not None:
        if existing.status is ExportStatus.READY and existing.expires_at and existing.expires_at <= now:
            existing.status = ExportStatus.EXPIRED
            db.commit()
        if existing.status in (ExportStatus.QUEUED, ExportStatus.RUNNING, ExportStatus.READY):
            return existing, False
        # failed / expired -> ugyanazt a sort indítjuk újra
        _reset_for_retry(existing, plan, now)
        db.commit()
        db.refresh(existing)
        return existing, True

    job = GalleryExportJob(
        public_id=str(uuid.uuid4()),
        project_id=project.id,
        client_id=client_id,
        source_fingerprint=plan.fingerprint,
        status=ExportStatus.QUEUED,
        file_count=plan.file_count,
        total_source_bytes=plan.total_source_bytes,
        expected_archive_bytes=plan.expected_archive_bytes,
        max_attempts=settings.export_max_attempts,
        next_attempt_at=now,
        filename=export_filename(project, plan.fingerprint),
        object_key=object_key_for(project.id, plan.fingerprint),
        created_by_employee_id=user.id,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        # Verseny: egy párhuzamos kérés ugyanezt a jobot már létrehozta.
        db.rollback()
        job = db.scalars(
            select(GalleryExportJob).where(
                GalleryExportJob.project_id == project.id,
                GalleryExportJob.source_fingerprint == plan.fingerprint,
            )
        ).one()
        return job, False
    db.refresh(job)
    return job, True


def _reset_for_retry(job: GalleryExportJob, plan: GalleryPlan, now: datetime) -> None:
    job.status = ExportStatus.QUEUED
    job.attempts = 0
    job.worker_id = None
    job.lease_expires_at = None
    job.next_attempt_at = now
    job.bytes_done = 0
    job.files_done = 0
    job.file_count = plan.file_count
    job.total_source_bytes = plan.total_source_bytes
    job.expected_archive_bytes = plan.expected_archive_bytes
    job.error_code = None
    job.error_message = None
    job.started_at = None
    job.ready_at = None
    job.finished_at = None
    job.expires_at = None
    job.object_size = None
    job.object_etag = None
    job.archive_sha256 = None


def current_job_for_project(
    db: Session, project: Project, *, storage: ObjectStorage | None = None
) -> GalleryExportJob | None:
    """A projekt AKTUÁLIS galéria-verziójához tartozó job (ha van).

    Ez teszi lehetővé, hogy az oldal bezárása/újranyitása után a UI ugyanazt a
    jobot találja meg - nem kell semmit a böngészőben tárolni.
    """
    try:
        plan = plan_gallery(db, project, storage=storage)
    except GalleryExportError:
        return None
    job = db.scalars(
        select(GalleryExportJob).where(
            GalleryExportJob.project_id == project.id,
            GalleryExportJob.source_fingerprint == plan.fingerprint,
        )
    ).first()
    if job is not None and job.status is ExportStatus.READY and job.expires_at and job.expires_at <= utcnow():
        job.status = ExportStatus.EXPIRED
        db.commit()
        db.refresh(job)
    return job


# --- Letöltési jegy ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DownloadTicket:
    url: str
    expires_at: datetime
    filename: str
    size: int
    etag: str
    sha256: str | None
    direct: bool


def _sign(payload: str) -> str:
    mac = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def make_download_token(job: GalleryExportJob, user_id: int, expires_at: datetime) -> str:
    exp = int(expires_at.timestamp())
    payload = f"{job.public_id}:{user_id}:{exp}"
    return f"{base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')}.{_sign(payload)}"


def parse_download_token(token: str) -> tuple[str, int, int]:
    """(public_id, user_id, exp) vagy ``GalleryExportError``."""
    try:
        body, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
        public_id, user_id, exp = payload.split(":")
    except Exception as exc:
        raise GalleryExportError("invalid_token", "Érvénytelen letöltési link.") from exc
    if not secrets.compare_digest(signature, _sign(payload)):
        raise GalleryExportError("invalid_token", "Érvénytelen letöltési link.")
    if int(exp) < int(time.time()):
        raise GalleryExportError("expired_token", "A letöltési link lejárt, kérj újat.")
    return public_id, int(user_id), int(exp)


def issue_download_ticket(
    db: Session,
    job: GalleryExportJob,
    user: Employee,
    storage: ObjectStorage,
    *,
    base_url: str,
) -> DownloadTicket:
    """Jogosultság-ellenőrzött letöltési URL kiadása.

    A link lejár (``EXPORT_DOWNLOAD_URL_TTL_SECONDS``), de **ugyanarra a
    változatlan objektumra** mutat: megújítás után a megszakadt letöltés
    Range-dzsel folytatható, mert az ETag és a méret nem változik.
    """
    assert_job_visible(db, job, user)
    if job.status is ExportStatus.EXPIRED:
        raise GalleryExportError("expired", "A csomag lejárt, kérj újat.")
    if job.status is not ExportStatus.READY or not job.object_key:
        raise GalleryExportError("not_ready", "A csomag még nem áll készen.")
    if job.expires_at and job.expires_at <= utcnow():
        job.status = ExportStatus.EXPIRED
        db.commit()
        raise GalleryExportError("expired", "A csomag lejárt, kérj újat.")

    expires_at = utcnow() + timedelta(seconds=settings.export_download_url_ttl_seconds)
    filename = job.filename or f"{job.public_id}.zip"

    presigned = None
    if storage.supports_presigned_urls:
        presigned = storage.presigned_download_url(
            job.object_key,
            expires_in=settings.export_download_url_ttl_seconds,
            filename=filename,
            content_type="application/zip",
        )

    if presigned:
        url = presigned
        direct = True
    else:
        token = make_download_token(job, user.id, expires_at)
        url = f"{base_url}/api/v1/gallery-exports/{job.public_id}/download?token={token}"
        direct = False

    return DownloadTicket(
        url=url,
        expires_at=expires_at,
        filename=filename,
        size=int(job.object_size or 0),
        etag=job.object_etag or "",
        sha256=job.archive_sha256,
        direct=direct,
    )


# --- Timeline esemény --------------------------------------------------------


def record_timeline(db: Session, job: GalleryExportJob, event_type: str, payload: dict) -> None:
    db.add(
        TimelineEvent(
            entity_type="GalleryExportJob",
            entity_id=job.id,
            event_type=event_type,
            payload=payload,
        )
    )


# --- Galéria-véglegesítési esemény -------------------------------------------


def prepare_export_on_gallery_finalized(
    db: Session, project_id: int, *, actor: Employee | None = None,
    storage: ObjectStorage | None = None,
) -> GalleryExportJob | None:
    """Csatlakozási pont a "galéria véglegesítve" eseményhez.

    Hívd meg például akkor, amikor a Portal ``live`` állapotba kerül, vagy a
    Deliverable ``anyag_kikuldve`` igaz lesz - így a csomag már a letöltési
    igény előtt elkészül. Hibát nem dob: üres galériánál csendben kihagyja.
    """
    project = db.get(Project, project_id)
    if project is None:
        return None
    system_user = actor or _system_actor(db)
    if system_user is None:
        return None
    try:
        job, _created = get_or_create_job(db, project, system_user, storage=storage)
    except GalleryExportError:
        return None
    return job


def _system_actor(db: Session) -> Employee | None:
    return db.scalars(
        select(Employee).where(Employee.role == SystemRole.ADMIN, Employee.is_active.is_(True))
    ).first()
