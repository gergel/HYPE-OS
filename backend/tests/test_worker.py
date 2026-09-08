"""Worker: hiba/újrapróbálás, stale job, forrásváltozás készülés közben, TTL-takarítás, párhuzamos elvétel."""

from __future__ import annotations

import os
from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.models.gallery_export import ExportErrorCode, ExportStatus, GalleryExportJob
from app.models.media import Media
from app.services.export_runner import _safe_delete
from app.services.gallery_export import get_or_create_job, utcnow
from app.services.storage.base import StorageError
from app.worker import claim_next_job, expire_and_cleanup, reclaim_stale_jobs, run_once
from tests.conftest import Seed


def _queued(seed: Seed, db, storage, project=None) -> GalleryExportJob:
    project = project or seed.project_a
    seed.small_gallery(project)
    job, created = get_or_create_job(db, project, seed.admin, storage=storage)
    assert created
    return job


def test_worker_failure_then_retry_succeeds(seed, db, storage, monkeypatch):
    job = _queued(seed, db, storage)
    original = storage.open_write
    calls = {"n": 0}

    def flaky(key, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise StorageError("szimulált tárhiba (pl. hálózat)")
        return original(key, **kwargs)

    monkeypatch.setattr(storage, "open_write", flaky)
    assert run_once(db, storage) == {"ready": 0, "failed": 0, "retry": 1}
    db.refresh(job)
    assert job.status is ExportStatus.QUEUED and job.attempts == 1
    assert job.error_code == "storage_error" and job.next_attempt_at > utcnow()
    assert run_once(db, storage) == {"ready": 0, "failed": 0, "retry": 0}, "backoff alatt nem fut"

    job.next_attempt_at = utcnow()
    db.commit()
    assert run_once(db, storage) == {"ready": 1, "failed": 0, "retry": 0}
    db.refresh(job)
    assert job.status is ExportStatus.READY and job.attempts == 2 and job.error_code is None
    assert storage.stat(job.object_key).size == job.object_size


def test_worker_gives_up_after_max_attempts(seed, db, storage, monkeypatch):
    job = _queued(seed, db, storage)
    monkeypatch.setattr(storage, "open_write", lambda *a, **k: (_ for _ in ()).throw(StorageError("mindig hibás")))
    for _ in range(settings.export_max_attempts):
        job.next_attempt_at = utcnow()
        db.commit()
        run_once(db, storage)
    db.refresh(job)
    assert job.status is ExportStatus.FAILED and job.attempts == settings.export_max_attempts
    assert job.error_code == "storage_error"
    assert not storage.exists(job.object_key)


def test_stale_running_job_is_reclaimed_and_finishes(seed, db, storage):
    job = _queued(seed, db, storage)
    # "elhalt worker": running, lejárt bérlettel
    job.status = ExportStatus.RUNNING
    job.attempts = 1
    job.worker_id = "halott:1"
    job.lease_expires_at = utcnow() - timedelta(seconds=5)
    db.commit()
    assert reclaim_stale_jobs(db) == 1
    db.refresh(job)
    assert job.status is ExportStatus.QUEUED and job.worker_id is None
    job.next_attempt_at = utcnow()
    db.commit()
    assert run_once(db, storage)["ready"] == 1


def test_stale_job_past_max_attempts_fails_with_stale_timeout(seed, db, storage):
    job = _queued(seed, db, storage)
    job.status = ExportStatus.RUNNING
    job.attempts = job.max_attempts
    job.lease_expires_at = utcnow() - timedelta(seconds=5)
    db.commit()
    reclaim_stale_jobs(db)
    db.refresh(job)
    assert job.status is ExportStatus.FAILED and job.error_code == str(ExportErrorCode.STALE_TIMEOUT)


def test_running_job_with_live_lease_is_not_reclaimed(seed, db, storage):
    job = _queued(seed, db, storage)
    job.status = ExportStatus.RUNNING
    job.lease_expires_at = utcnow() + timedelta(seconds=60)
    db.commit()
    assert reclaim_stale_jobs(db) == 0
    assert claim_next_job(db, wid="x") is None


def test_missing_source_fails_not_masked(seed, db, storage):
    job = _queued(seed, db, storage)
    media = db.scalars(select(Media).where(Media.project_id == seed.project_a.id)).first()
    storage.delete(media.storage_key)
    assert run_once(db, storage) == {"ready": 0, "failed": 1, "retry": 0}
    db.refresh(job)
    assert job.status is ExportStatus.FAILED and job.error_code == "source_missing"
    assert media.storage_key in job.error_message
    assert not storage.exists(job.object_key), "nem marad fél csomag"


def test_source_truncated_during_packaging_fails(seed, db, storage, monkeypatch):
    """A worker olvasás közben a forrás megváltozik (rövidebb lesz) -> nem lehet siker."""
    job = _queued(seed, db, storage)
    media = db.scalars(select(Media).where(Media.project_id == seed.project_a.id)).all()[2]
    original = storage.read_stream

    def read_and_truncate(key, **kwargs):
        if key == media.storage_key:
            path = storage._path(key)
            with open(path, "r+b") as fh:
                fh.truncate(100)
        return original(key, **kwargs)

    monkeypatch.setattr(storage, "read_stream", read_and_truncate)
    assert run_once(db, storage)["failed"] == 1
    db.refresh(job)
    assert job.status is ExportStatus.FAILED and job.error_code == "source_changed"
    assert "lerövidült" in job.error_message
    assert not storage.exists(job.object_key)


def test_gallery_changed_during_packaging_is_rejected_at_the_end(seed, db, storage, monkeypatch):
    """Új fájl kerül a galériába csomagolás közben -> a végső ujjlenyomat eltér -> hibás, csomag eldobva."""
    job = _queued(seed, db, storage)
    original = storage.read_stream
    injected = {"done": False}

    def read_and_inject(key, **kwargs):
        if not injected["done"]:
            injected["done"] = True
            seed.add_media(seed.project_a, "kozben-feltoltott", b"x" * 500)
        return original(key, **kwargs)

    monkeypatch.setattr(storage, "read_stream", read_and_inject)
    assert run_once(db, storage)["failed"] == 1
    db.refresh(job)
    assert job.status is ExportStatus.FAILED and job.error_code == "source_changed"
    assert not storage.exists(job.object_key)


def test_ttl_cleanup_deletes_only_export_never_sources(seed, db, storage):
    job = _queued(seed, db, storage)
    assert run_once(db, storage)["ready"] == 1
    db.refresh(job)
    assert job.expires_at - job.ready_at == timedelta(hours=settings.export_ttl_hours)
    assert expire_and_cleanup(db, storage) == {"expired": 0, "objects_deleted": 0}, "TTL előtt nem takarít"

    job.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    sources = list(seed.files[seed.project_a.id])
    assert expire_and_cleanup(db, storage) == {"expired": 1, "objects_deleted": 1}
    db.refresh(job)
    assert job.status is ExportStatus.EXPIRED
    assert not storage.exists(job.object_key)
    for key in sources:
        assert storage.exists(key), "az eredeti média soha nem törlődik"


def test_safe_delete_refuses_non_export_keys(seed, db, storage):
    seed.small_gallery(seed.project_a)
    key = next(iter(seed.files[seed.project_a.id]))
    _safe_delete(storage, key)
    assert storage.exists(key)
    _safe_delete(storage, "")
    assert settings.media_object_prefix != settings.export_object_prefix


def test_concurrent_claim_only_one_wins(seed, db, storage):
    from app.core import database

    _queued(seed, db, storage)
    other = database.SessionLocal()
    try:
        first = claim_next_job(db, wid="w1")
        second = claim_next_job(other, wid="w2")
        assert first is not None and second is None
        assert first.worker_id == "w1" and first.attempts == 1 and first.status is ExportStatus.RUNNING
    finally:
        other.close()


def test_worker_memory_stays_bounded_for_large_file(seed, db, storage, monkeypatch):
    """A worker nem tölti a fájlt a memóriába: a bejövő darabok mérete a chunk-korlát."""

    seen = {"max_chunk": 0}
    original = storage.read_stream

    def measuring(key, **kwargs):
        for chunk in original(key, **kwargs):
            seen["max_chunk"] = max(seen["max_chunk"], len(chunk))
            yield chunk

    monkeypatch.setattr(storage, "read_stream", measuring)
    seed.add_media(seed.project_a, "nagy", os.urandom(3 * 1024 * 1024))
    get_or_create_job(db, seed.project_a, seed.admin, storage=storage)
    assert run_once(db, storage)["ready"] == 1
    assert seen["max_chunk"] == settings.export_chunk_bytes
