"""Privát fájlrendszer-alapú objektumtár.

Nem publikus statikus könyvtár: a FastAPI soha nem szolgálja ki közvetlenül,
csak a jogosultság-ellenőrzött, Range-képes letöltő végponton keresztül.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.services.storage.base import (
    ObjectNotFound,
    StorageError,
    StoredObject,
    WriteResult,
)


def _validate_key(key: str) -> str:
    """Kulcs-normalizálás + path traversal elleni védelem."""
    if not key or key.startswith("/") or "\\" in key:
        raise StorageError(f"Érvénytelen tárkulcs: {key!r}")
    parts = key.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise StorageError(f"Érvénytelen tárkulcs: {key!r}")
    return key


class _LocalWriter:
    """Csak-írható, nem kereshető kimenet ideiglenes fájlba, sha256-számlálóval."""

    __slots__ = ("_fh", "_hash", "_size")

    def __init__(self, fh) -> None:
        self._fh = fh
        self._hash = hashlib.sha256()
        self._size = 0

    def write(self, data: bytes, /) -> int:
        if not data:
            return 0
        view = memoryview(data)
        self._fh.write(view)
        self._hash.update(view)
        self._size += len(view)
        return len(view)

    @property
    def size(self) -> int:
        return self._size

    @property
    def sha256(self) -> str:
        return self._hash.hexdigest()


class LocalObjectStorage:
    """``ObjectStorage`` implementáció helyi, privát könyvtár felett."""

    supports_presigned_urls = False

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        _validate_key(key)
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root) + os.sep):
            raise StorageError(f"A kulcs kilépne a tárgyökérből: {key!r}")
        return path

    # --- olvasás ---------------------------------------------------------

    def stat(self, key: str) -> StoredObject:
        path = self._path(key)
        try:
            st = path.stat()
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc
        # Stabil, tartalomhoz kötött azonosság: méret + mtime_ns + inode.
        etag = hashlib.sha256(
            f"{st.st_size}:{st.st_mtime_ns}:{st.st_ino}".encode()
        ).hexdigest()[:32]
        return StoredObject(key=key, size=st.st_size, etag=etag)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def read_stream(
        self, key: str, *, offset: int = 0, length: int | None = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> Iterator[bytes]:
        path = self._path(key)
        try:
            fh = path.open("rb")
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc
        with fh:
            if offset:
                fh.seek(offset)
            remaining = length
            while True:
                want = chunk_size if remaining is None else min(chunk_size, remaining)
                if want <= 0:
                    return
                data = fh.read(want)
                if not data:
                    return
                if remaining is not None:
                    remaining -= len(data)
                yield data

    # --- írás ------------------------------------------------------------

    @contextmanager
    def open_write(self, key: str, *, content_type: str = "application/octet-stream"):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".partial-", suffix=".tmp")
        tmp_path = Path(tmp_name)
        holder = _WriteHolder()
        try:
            with os.fdopen(fd, "wb", buffering=1024 * 1024) as fh:
                writer = _LocalWriter(fh)
                holder.stream = writer
                yield holder
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        st = self.stat(key)
        holder.result = WriteResult(key=key, size=writer.size, etag=st.etag, sha256=writer.sha256)

    # --- törlés ----------------------------------------------------------

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def presigned_download_url(
        self, key: str, *, expires_in: int, filename: str | None = None,
        content_type: str = "application/zip",
    ) -> str | None:
        return None


class _WriteHolder:
    """A ``open_write`` context manager által kiadott doboz (stream + eredmény)."""

    __slots__ = ("result", "stream")

    def __init__(self) -> None:
        self.stream = None
        self.result: WriteResult | None = None

    def write(self, data: bytes, /) -> int:
        return self.stream.write(data)
