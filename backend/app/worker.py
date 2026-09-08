"""Galéria-export worker - tartós háttérfeladat-futtató.

Indítás::

    python -m app.worker                      # folyamatos futás
    python -m app.worker --concurrency 4      # több párhuzamos job
    python -m app.worker --once               # a jelenlegi sor feldolgozása, majd kilépés
    python -m app.worker cleanup              # csak TTL-lejárat + takarítás
    python -m app.worker backfill-sizes       # hiányzó Media.size_bytes pótlása a tárból

A worker **külön processz**: sem a web-kérés, sem a böngésző nem csomagol.
A sor az adatbázisban van, ezért a worker (és a web) újraindítása után is
folytatódik a munka.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading
import time
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.gallery_export import ExportErrorCode, ExportStatus, GalleryExportJob
from app.models.media import Media
from app.services.export_runner import ExportFailure, finalize_ready, run_export_job
from app.services.gallery_export import record_timeline, utcnow
from app.services.storage import ObjectNotFound, build_storage

logger = logging.getLogger("hype.export.worker")

#: Újrapróbálkozási várakozás felső korlátja.
MAX_BACKOFF_SECONDS = 900


def worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"


# --- sorkezelés --------------------------------------------------------------


def claim_next_job(db: Session, *, wid: str) -> GalleryExportJob | None:
    """Egy várakozó job atomikus elvétele.

    Az elvétel egyetlen feltételes ``UPDATE``, ezért versenymentes PostgreSQL-en
    és SQLite-on is: két worker közül csak az egyik ``rowcount``-ja lesz 1.
    """
    now = utcnow()
    candidate = db.scalars(
        select(GalleryExportJob)
        .where(
            GalleryExportJob.status == ExportStatus.QUEUED,
            or_(
                GalleryExportJob.next_attempt_at.is_(None),
                GalleryExportJob.next_attempt_at <= now,
            ),
        )
        .order_by(GalleryExportJob.next_attempt_at, GalleryExportJob.id)
        .limit(1)
    ).first()
    if candidate is None:
        return None

    job_id = candidate.id
    result = db.execute(
        update(GalleryExportJob)
        .where(
            GalleryExportJob.id == job_id,
            GalleryExportJob.status == ExportStatus.QUEUED,
        )
        .values(
            status=ExportStatus.RUNNING,
            worker_id=wid,
            attempts=GalleryExportJob.attempts + 1,
            started_at=now,
            lease_expires_at=now + timedelta(seconds=settings.export_lease_seconds),
            bytes_done=0,
            files_done=0,
            error_code=None,
            error_message=None,
        )
    )
    db.commit()
    if result.rowcount != 1:
        return None  # másik worker gyorsabb volt
    db.expire_all()
    return db.get(GalleryExportJob, job_id)


def reclaim_stale_jobs(db: Session) -> int:
    """Elhalt worker után maradt ``running`` jobok visszaküldése a sorba."""
    now = utcnow()
    stale = list(
        db.scalars(
            select(GalleryExportJob).where(
                GalleryExportJob.status == ExportStatus.RUNNING,
                GalleryExportJob.lease_expires_at.isnot(None),
                GalleryExportJob.lease_expires_at < now,
            )
        )
    )
    for job in stale:
        if job.attempts >= job.max_attempts:
            _mark_failed(
                db, job, ExportErrorCode.STALE_TIMEOUT,
                f"A feldolgozás {job.attempts} próbálkozás után megszakadt (elhalt worker).",
            )
        else:
            job.status = ExportStatus.QUEUED
            job.worker_id = None
            job.lease_expires_at = None
            job.next_attempt_at = now + timedelta(seconds=_backoff(job.attempts))
            logger.warning("Stale job visszakerült a sorba: %s (attempt=%s)", job.public_id, job.attempts)
    if stale:
        db.commit()
    return len(stale)


def _backoff(attempts: int) -> int:
    return min(30 * (2 ** max(attempts - 1, 0)), MAX_BACKOFF_SECONDS)


def _mark_failed(db: Session, job: GalleryExportJob, code: ExportErrorCode, message: str) -> None:
    job.status = ExportStatus.FAILED
    job.error_code = str(code)
    job.error_message = message[:2000]
    job.finished_at = utcnow()
    job.worker_id = None
    job.lease_expires_at = None
    record_timeline(db, job, "GalleryExportFailed",
                    {"project_id": job.project_id, "public_id": job.public_id, "error_code": str(code)})
    db.commit()


# --- TTL / takarítás ---------------------------------------------------------


def expire_and_cleanup(db: Session, storage=None) -> dict:
    """Lejárt csomagok megjelölése és **biztonságos** törlése.

    Csak az ``EXPORT_OBJECT_PREFIX`` alatti objektumokat törli; az eredeti
    médiafájlokat soha nem érinti (a törlés kulcs-prefixre ellenőrzött).
    """
    storage = storage or build_storage()
    now = utcnow()
    expired = list(
        db.scalars(
            select(GalleryExportJob).where(
                GalleryExportJob.status == ExportStatus.READY,
                GalleryExportJob.expires_at.isnot(None),
                GalleryExportJob.expires_at <= now,
            )
        )
    )
    deleted = 0
    for job in expired:
        key = job.object_key or ""
        if key.startswith(settings.export_object_prefix):
            try:
                storage.delete(key)
                deleted += 1
            except Exception:
                logger.warning("Lejárt csomag törlése sikertelen: %s", key, exc_info=True)
        else:
            logger.error("Törlés megtagadva, nem export-prefixű kulcs: %r", key)
        job.status = ExportStatus.EXPIRED
        job.finished_at = now
        record_timeline(db, job, "GalleryExportExpired",
                        {"project_id": job.project_id, "public_id": job.public_id})
    if expired:
        db.commit()
    return {"expired": len(expired), "objects_deleted": deleted}


def backfill_media_sizes(db: Session, storage=None, *, project_id: int | None = None) -> dict:
    """A hiányzó ``Media.size_bytes`` mezők pótlása a tárból (nem törli az eredetit)."""
    storage = storage or build_storage()
    query = select(Media).where(Media.size_bytes.is_(None))
    if project_id is not None:
        query = query.where(Media.project_id == project_id)
    filled, missing = 0, 0
    for media in db.scalars(query):
        try:
            media.size_bytes = storage.stat(media.storage_key).size
            filled += 1
        except ObjectNotFound:
            missing += 1
            logger.warning("Hiányzó forrásobjektum: media_id=%s key=%s", media.id, media.storage_key)
    db.commit()
    return {"filled": filled, "missing": missing}


# --- egy job végrehajtása ----------------------------------------------------


def process_job(db: Session, job: GalleryExportJob, storage) -> str:
    """Egy elvett job végigvitele. Visszaadja a végállapot nevét."""
    try:
        outcome = run_export_job(db, job, storage)
    except ExportFailure as failure:
        db.rollback()
        db.expire_all()
        job = db.get(GalleryExportJob, job.id)
        if failure.retryable and job.attempts < job.max_attempts:
            job.status = ExportStatus.QUEUED
            job.worker_id = None
            job.lease_expires_at = None
            job.next_attempt_at = utcnow() + timedelta(seconds=_backoff(job.attempts))
            job.error_code = str(failure.code)
            job.error_message = failure.message[:2000]
            db.commit()
            logger.warning("Job újrapróbálásra várakozik: %s (%s)", job.public_id, failure.code)
            return "retry"
        _mark_failed(db, job, failure.code, failure.message)
        logger.error("Job végleg elbukott: %s (%s) %s", job.public_id, failure.code, failure.message)
        return "failed"
    finalize_ready(db, job, outcome)
    logger.info(
        "Job kész: %s files=%s bytes=%s sha256=%s %.1fs",
        job.public_id, outcome.files, outcome.size, outcome.sha256[:12], outcome.duration_seconds,
    )
    return "ready"


def run_once(db: Session | None = None, storage=None, *, limit: int | None = None) -> dict:
    """A pillanatnyi sor feldolgozása egy szálon (tesztekhez és cron-hoz)."""
    own_session = db is None
    db = db or SessionLocal()
    storage = storage or build_storage()
    counts = {"ready": 0, "failed": 0, "retry": 0}
    try:
        reclaim_stale_jobs(db)
        processed = 0
        while limit is None or processed < limit:
            job = claim_next_job(db, wid=worker_id())
            if job is None:
                break
            counts[process_job(db, job, storage)] += 1
            processed += 1
    finally:
        if own_session:
            db.close()
    return counts


# --- folyamatos futás --------------------------------------------------------


class WorkerLoop:
    def __init__(self, *, concurrency: int, poll_seconds: float) -> None:
        self.concurrency = max(1, concurrency)
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._last_maintenance = 0.0

    def stop(self, *_args) -> None:
        logger.info("Leállítási jelzés megérkezett, a futó job befejeződik...")
        self._stop.set()

    def _thread(self, index: int) -> None:
        wid = f"{socket.gethostname()}:{os.getpid()}:t{index}"
        db = SessionLocal()
        storage = build_storage()
        try:
            while not self._stop.is_set():
                try:
                    job = claim_next_job(db, wid=wid)
                except Exception:
                    logger.exception("Hiba a sor olvasásakor")
                    db.rollback()
                    self._stop.wait(self.poll_seconds)
                    continue
                if job is None:
                    self._stop.wait(self.poll_seconds)
                    continue
                try:
                    process_job(db, job, storage)
                except Exception:
                    logger.exception("Váratlan hiba a job feldolgozásakor: %s", job.public_id)
                    db.rollback()
        finally:
            db.close()

    def _maintenance(self) -> None:
        db = SessionLocal()
        storage = build_storage()
        try:
            reclaim_stale_jobs(db)
            expire_and_cleanup(db, storage)
        except Exception:
            logger.exception("Karbantartási ciklus hibája")
            db.rollback()
        finally:
            db.close()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        logger.info(
            "Export worker indul: concurrency=%s backend=%s ttl=%sh",
            self.concurrency, settings.storage_backend, settings.export_ttl_hours,
        )
        threads = [
            threading.Thread(target=self._thread, args=(i,), name=f"export-{i}", daemon=True)
            for i in range(self.concurrency)
        ]
        for thread in threads:
            thread.start()
        while not self._stop.is_set():
            now = time.monotonic()
            if now - self._last_maintenance > 30:
                self._last_maintenance = now
                self._maintenance()
            self._stop.wait(1.0)
        for thread in threads:
            thread.join(timeout=60)
        logger.info("Export worker leállt.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description="HYPE OS galéria-export worker")
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "cleanup", "backfill-sizes"])
    parser.add_argument("--concurrency", type=int, default=settings.export_worker_concurrency)
    parser.add_argument("--poll-interval", type=float, default=settings.export_worker_poll_seconds)
    parser.add_argument("--once", action="store_true", help="A jelenlegi sor feldolgozása, majd kilépés.")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )

    if args.command == "cleanup":
        db = SessionLocal()
        try:
            print(expire_and_cleanup(db))
        finally:
            db.close()
        return 0

    if args.command == "backfill-sizes":
        db = SessionLocal()
        try:
            print(backfill_media_sizes(db, project_id=args.project_id))
        finally:
            db.close()
        return 0

    if args.once:
        print(run_once())
        return 0

    WorkerLoop(concurrency=args.concurrency, poll_seconds=args.poll_interval).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
