"""Objektumtár-factory: a ``STORAGE_BACKEND`` beállítás alapján ad klienst."""

from __future__ import annotations

import threading

from app.core.config import settings
from app.services.storage.base import (
    ObjectNotFound,
    ObjectStorage,
    StorageError,
    StoredObject,
    WriteResult,
)
from app.services.storage.local import LocalObjectStorage
from app.services.storage.s3 import S3ObjectStorage, content_disposition

_lock = threading.Lock()
_instance: ObjectStorage | None = None
_instance_signature: tuple | None = None


def build_storage() -> ObjectStorage:
    """Új tárkliens a jelenlegi beállításokból (teszt/worker használja)."""
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalObjectStorage(settings.local_storage_root)
    if backend in ("s3", "r2"):
        return S3ObjectStorage(
            bucket=settings.r2_bucket_name,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.r2_access_key_id,
            secret_key=settings.r2_secret_access_key,
            region=settings.r2_region,
            part_bytes=settings.export_s3_multipart_part_bytes,
        )
    raise StorageError(
        f"Ismeretlen STORAGE_BACKEND: {settings.storage_backend!r} (várt: 'local' vagy 's3')"
    )


def get_storage() -> ObjectStorage:
    """Folyamatonként megosztott tárkliens (a beállítás változásakor újraépül)."""
    global _instance, _instance_signature
    signature = (settings.storage_backend, settings.local_storage_root, settings.r2_bucket_name,
                 settings.s3_endpoint_url)
    with _lock:
        if _instance is None or _instance_signature != signature:
            _instance = build_storage()
            _instance_signature = signature
        return _instance


def reset_storage_cache() -> None:
    """Tesztekhez: a következő ``get_storage()`` újraépíti a klienst."""
    global _instance, _instance_signature
    with _lock:
        _instance = None
        _instance_signature = None


__all__ = [
    "LocalObjectStorage",
    "ObjectNotFound",
    "ObjectStorage",
    "S3ObjectStorage",
    "StorageError",
    "StoredObject",
    "WriteResult",
    "build_storage",
    "content_disposition",
    "get_storage",
    "reset_storage_cache",
]
