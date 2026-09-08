"""Objektumtár-absztrakció.

A HYPE OS-ben a média (és a belőle képzett galéria-export) **nem** a relációs
adatbázisban, hanem egy privát objektumtárban él; az adatbázisban csak a
``storage_key`` van. Ez a réteg két háttértárat ad ugyanazzal a felülettel:

* ``local`` - privát fájlrendszer-könyvtár (fejlesztés, CI, on-prem futtatás),
* ``s3``    - Cloudflare R2 vagy bármely S3-kompatibilis **privát** bucket.

Szándékosan nincs feltételezve, hogy a fájlok S3-ban vannak: a repóban eddig
egyáltalán nem volt tárkliens, a ``local`` backend a teljes exportot és
letöltést fizetős erőforrás nélkül futtathatóvá teszi.

Minden művelet **streamelt**: sem az olvasás, sem az írás nem tölt egész fájlt
memóriába.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Általános tárhiba."""


class ObjectNotFound(StorageError):
    """A kért kulcs nem létezik a tárban."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Objektum nem található: {key}")
        self.key = key


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Egy objektum azonossága a tárban."""

    key: str
    size: int
    etag: str


@dataclass(slots=True)
class WriteResult:
    """Egy befejezett streamelt írás eredménye."""

    key: str
    size: int
    etag: str
    sha256: str


@runtime_checkable
class WritableStream(Protocol):
    """Csak-írható, nem kereshető (non-seekable) kimenet."""

    def write(self, data: bytes, /) -> int: ...


class ObjectStorage(Protocol):
    """A tárkliensek közös felülete."""

    #: Igaz, ha a backend tud saját, aláírt (presigned) letöltési URL-t adni.
    supports_presigned_urls: bool

    def stat(self, key: str) -> StoredObject:
        """Objektum mérete/ETag-je. ``ObjectNotFound``, ha nincs ilyen kulcs."""

    def exists(self, key: str) -> bool: ...

    def read_stream(self, key: str, *, offset: int = 0, length: int | None = None,
                    chunk_size: int = 8 * 1024 * 1024) -> Iterator[bytes]:
        """Byte-tartomány streamelt olvasása. Konstans memóriahasználat."""

    def open_write(self, key: str, *, content_type: str = "application/octet-stream"):
        """Context manager, ami egy ``WritableStream``-et ad.

        Kilépéskor (kivétel nélkül) atomikusan véglegesíti az objektumot, és a
        context manager ``result`` attribútumában adja vissza a ``WriteResult``-ot.
        Kivétel esetén a részleges objektumot eldobja (nem hagy fél objektumot).
        """

    def delete(self, key: str) -> None:
        """Objektum törlése. Nem hiba, ha már nincs meg."""

    def presigned_download_url(
        self,
        key: str,
        *,
        expires_in: int,
        filename: str | None = None,
        content_type: str = "application/zip",
    ) -> str | None:
        """Aláírt, közvetlen letöltési URL, vagy ``None``, ha a backend nem tudja."""
