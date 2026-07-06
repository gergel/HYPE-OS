"""Celery worker: aszinkron videó-feldolgozás (FFmpeg) a Média Portálhoz - a
Hype-repo-main (különálló client-portál projekt) workers/tasks.py 1:1 portolt
logikája. Külön Railway service-ként fut ("celery -A app.workers.portal_tasks
worker"), a meglévő settings.redis_url brókeren keresztül a fő API service-től
függetlenül - a videó-transzkódolás percekig tarthat, ez NEM futhat a
kérés/válasz ciklusban."""

from __future__ import annotations

import os
import tempfile

from celery import Celery

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.portal import PortalVideo
from app.services import portal_storage as storage
from app.services import portal_transcode as transcode

celery_app = Celery("hype_portal", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_track_started = True


@celery_app.task(name="portal.process_video")
def process_video_task(video_id: int, source_key: str) -> None:
    """Gyors lépés: metaadat + borító (első frame), a videó azonnal nézhető
    marad. Majd elindítja a háttér HLS-feldolgozást külön taskban."""
    db = SessionLocal()
    try:
        video = db.get(PortalVideo, video_id)
        if not video:
            return

        video.mp4_url = storage.public_url(source_key)
        video.source_key = source_key
        try:
            video.size_bytes = storage.head_size(source_key)
        except Exception:
            pass

        remote = storage.presigned_get(source_key)
        try:
            info = transcode.quick_metadata_and_thumb(remote, f"videos/{video_id}")
            for k, v in info.items():
                setattr(video, k, v)
        except Exception:
            # ha a borító/metaadat se megy, akkor is nézhető marad az mp4
            pass

        video.status = "ready"
        db.commit()

        build_hls_task.delay(video_id, source_key)
    finally:
        db.close()


@celery_app.task(name="portal.build_hls", soft_time_limit=10800, time_limit=11000)
def build_hls_task(video_id: int, source_key: str) -> None:
    """Lassú lépés: HLS generálás. Ha elhasal, a videó marad 'ready' az mp4-gyel."""
    db = SessionLocal()
    try:
        video = db.get(PortalVideo, video_id)
        if not video:
            return
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "source.mp4")
            storage.download_to(source_key, src)
            hls_url = transcode.build_hls(src, f"videos/{video_id}")
        video = db.get(PortalVideo, video_id)
        if video:
            video.hls_url = hls_url
            db.commit()
    except Exception:
        pass
    finally:
        db.close()
