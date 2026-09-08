"""Streaming exports for the live portal. No browser buffers or web request packaging."""
from __future__ import annotations
import hashlib
import json
import logging
import time
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.portal import Portal, PortalImage, PortalVideo
from app.models.portal_export import PortalExport
from app.services import portal_storage as storage
from app.services.export_storage.s3 import S3ObjectStorage
from app.services.zip64 import ArcNameAllocator, PlannedEntry, Zip64Writer, sanitize_component

log = logging.getLogger(__name__)
PREFIX = 'portal-exports/'

def now():
    return datetime.now(timezone.utc)

def object_store():
    return S3ObjectStorage(bucket=settings.r2_bucket_name,
        endpoint_url=f'https://{settings.r2_account_id}.r2.cloudflarestorage.com',
        access_key=settings.r2_access_key_id, secret_key=settings.r2_secret_access_key,
        part_bytes=32 * 1024 * 1024)

def descriptor(item, kind, path):
    key = item.key if kind == 'image' else item.source_key
    if not key:
        raise ValueError('Egy eredeti fájl még nem érhető el.')
    return dict(id=item.id, kind=kind, key=storage._key(key), path=path,
        updated=str(item.updated_at), size=int(item.size_bytes or 0))

def make_manifest(db, images, videos):
    names = ArcNameAllocator()
    result = []
    for kind, model, entries in [('image', PortalImage, images), ('video', PortalVideo, videos)]:
        for entry in entries:
            item = db.get(model, entry.id)
            key = item.key if kind == 'image' else item.source_key
            ext = PurePosixPath(key or '').suffix or ('.jpg' if kind == 'image' else '.mp4')
            title = sanitize_component(item.title or f'{kind}-{item.id}')
            if not title.lower().endswith(ext.lower()):
                title += ext
            # Directory labels are cosmetic, never filesystem/storage paths.
            folder = sanitize_component(entry.folder) if entry.folder else ''
            path = names.allocate(f'{folder}/{title}' if folder else title)
            result.append(descriptor(item, kind, path))
    return result

def current_sources(db, manifest):
    for entry in manifest:
        model = PortalImage if entry['kind'] == 'image' else PortalVideo
        item = db.get(model, entry['id'])
        if item is None or descriptor(item, entry['kind'], entry['path']) != entry:
            raise ValueError('A forrás megváltozott. Kérj új csomagot.')

def request_export(db, portal_id, manifest, filename):
    fingerprint = hashlib.sha256(json.dumps([portal_id, manifest], sort_keys=True).encode()).hexdigest()
    job = db.scalar(select(PortalExport).where(PortalExport.fingerprint == fingerprint).with_for_update())
    if job and job.state == 'ready' and job.expires_at and job.expires_at <= now():
        # Keep the expired key for cleanup before reusing this row.
        if job.object_key:
            safe_delete(job.object_key)
        job.state = 'expired'
    if job and job.state in ('failed', 'expired'):
        job.state = 'queued'; job.attempts = 0; job.error = None
        job.object_key = None; job.bytes_done = 0; job.expires_at = None
        job.touched_at = now()
        db.commit()
    if job is None:
        active = db.scalar(select(func.count()).select_from(PortalExport).where(
            PortalExport.portal_id == portal_id, PortalExport.state.in_(['queued', 'running'])))
        if active >= 4:
            raise ValueError('Már készülnek csomagok ehhez a portálhoz. Próbáld újra később.')
        job = PortalExport(id=str(uuid.uuid4()), portal_id=portal_id, fingerprint=fingerprint,
            manifest=manifest, filename=sanitize_component(filename or 'anyagok') + '.zip',
            state='queued', attempts=0, total_bytes=sum(e['size'] for e in manifest),
            bytes_done=0, object_size=0, touched_at=now())
        db.add(job)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            job = db.scalar(select(PortalExport).where(PortalExport.fingerprint == fingerprint))
    if job.state == 'queued':
        try:
            from app.workers.portal_export_tasks import build_export
            build_export.delay(job.id)
        except Exception:
            # Durable queue is recovered by beat even if Redis is temporarily down.
            log.exception('Export dispatch deferred')
    return job

def safe_delete(key):
    if not key or not key.startswith(PREFIX):
        raise ValueError('Not an export object')
    object_store().delete(key)

def run_export(job_id):
    owner = str(uuid.uuid4())
    key = f'{PREFIX}{job_id}/{owner}.zip'
    with SessionLocal() as db:
        won = db.execute(update(PortalExport).where(PortalExport.id == job_id,
            PortalExport.state == 'queued').values(state='running', owner=owner,
            touched_at=now(), attempts=PortalExport.attempts + 1, bytes_done=0))
        db.commit()
        if won.rowcount != 1:
            return
        job = db.get(PortalExport, job_id)
        manifest = job.manifest
        stop = threading.Event()
        def heartbeat():
            while not stop.wait(30):
                try:
                    with SessionLocal() as lease_db:
                        lease_db.execute(update(PortalExport).where(PortalExport.id == job_id,
                            PortalExport.owner == owner, PortalExport.state == 'running').values(touched_at=now()))
                        lease_db.commit()
                except Exception:
                    log.exception('Export heartbeat failed')
        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        try:
            current_sources(db, manifest)
            client = storage._client()
            heads = [client.head_object(Bucket=settings.r2_bucket_name, Key=e['key']) for e in manifest]
            total = sum(h['ContentLength'] for h in heads)
            job.total_bytes = total; db.commit()
            done = 0
            last = 0.0
            def progress(count):
                nonlocal done, last
                done += count
                if time.monotonic() - last > 2:
                    last = time.monotonic()
                    changed = db.execute(update(PortalExport).where(PortalExport.id == job_id,
                        PortalExport.owner == owner, PortalExport.state == 'running').values(bytes_done=done, touched_at=now()))
                    db.commit()
                    if changed.rowcount != 1:
                        raise ValueError('Export lease lost')
            def chunks(entry, head):
                body = client.get_object(Bucket=settings.r2_bucket_name, Key=entry['key'], IfMatch=head['ETag'])['Body']
                try:
                    while data := body.read(4 * 1024 * 1024):
                        yield data
                finally:
                    body.close()
            store = object_store()
            with store.open_write(key, content_type='application/zip') as sink:
                writer = Zip64Writer(sink, on_progress=progress)
                for entry, head in zip(manifest, heads):
                    writer.add_stream(PlannedEntry(entry['path'], head['ContentLength'], datetime(2026, 1, 1)), chunks(entry, head))
                writer.close()
            # A same-size overwrite is detected too; GET was pinned with If-Match.
            for entry, head in zip(manifest, heads):
                check = client.head_object(Bucket=settings.r2_bucket_name, Key=entry['key'])
                if check['ETag'] != head['ETag']:
                    raise ValueError('A forrás csomagolás közben megváltozott.')
            db.expire_all(); current_sources(db, manifest)
            changed = db.execute(update(PortalExport).where(PortalExport.id == job_id,
                PortalExport.owner == owner, PortalExport.state == 'running').values(
                state='ready', object_key=key, object_size=sink.result.size, sha256=sink.result.sha256,
                bytes_done=total, touched_at=now(), expires_at=now() + timedelta(hours=48), error=None))
            db.commit()
            if changed.rowcount != 1:
                safe_delete(key)
        except Exception as exc:
            db.rollback()
            log.exception('Portal export failed: %s', job_id)
            try:
                safe_delete(key)
            except Exception:
                log.exception('Export cleanup failed')
            db.execute(update(PortalExport).where(PortalExport.id == job_id, PortalExport.owner == owner).values(
                state='failed' if isinstance(exc, ValueError) or job.attempts >= 3 else 'queued',
                error='A csomag nem készült el. Próbáld újra; ha ismét hibás, jelezd nekünk.', touched_at=now()))
            db.commit()
        finally:
            stop.set()
            pulse.join(timeout=5)

def maintain_exports():
    with SessionLocal() as db:
        # No live worker may publish after its lease has been superseded.
        stale = db.scalars(select(PortalExport).where(PortalExport.state == 'running',
            PortalExport.touched_at < now() - timedelta(minutes=15)).with_for_update(skip_locked=True)).all()
        for job in stale:
            job.state = 'queued' if job.attempts < 3 else 'failed'
            job.owner = None; job.touched_at = now()
        expired = db.scalars(select(PortalExport).where(PortalExport.state == 'ready',
            PortalExport.expires_at < now()).with_for_update(skip_locked=True)).all()
        for job in expired:
            safe_delete(job.object_key)
            job.state = 'expired'; job.object_key = None
        db.commit()
        ids = db.scalars(select(PortalExport.id).where(PortalExport.state == 'queued',
            PortalExport.touched_at < now() - timedelta(seconds=60)).limit(10)).all()
        from app.workers.portal_export_tasks import build_export
        for job_id in ids:
            build_export.delay(job_id)
