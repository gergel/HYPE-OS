"""Streamelt ZIP64 archívumíró (STORE mód) és fájlnév-fertőtlenítés.

Miért saját író a ``zipfile`` helyett?

* **Konstans memória, seek nélkül.** Az író egyetlen, csak-írható kimenetbe
  (fájl, S3 multipart) ír; sosem kell visszalépni, így a csomag közvetlenül a
  privát objektumtárba streamelhető, staging lemez nélkül.
* **Pontosan előre számítható méret.** STORE módban minden bájt előre ismert,
  így a job már induláskor tudja a végleges ``Content-Length``-et, a UI valós
  százalékot mutat, és a végén bájtra pontos önellenőrzés van
  (``predict_archive_size`` == ténylegesen kiírt bájtszám).
* **Determinisztikus kimenet.** Ugyanaz a galéria-verzió ugyanazt a bájtsorozatot
  adja -> stabil ``sha256`` / objektumazonosság, újrafuttatás után is folytatható
  letöltés.

Két írásmód:

* ``DATA_DESCRIPTOR`` (alapértelmezett): egy menetes írás, a CRC32 a fájl után,
  ZIP64 data descriptorban (8 bájtos méretmezők). A forrást egyszer olvassuk.
* ``CRC_IN_HEADER``: a CRC a lokális fejlécbe kerül, ezért a forrást **kétszer**
  olvassuk (első menet: CRC + méret, második: adat). Csak akkor kell, ha egy
  legacy kliens nem tud data descriptort olvasni; kétszeres olvasási költség.

Az archívum mindig tartalmaz ZIP64 end-of-central-directory rekordot és
locatort, a ZIP64 extra mezők pedig ott jelennek meg, ahol a spec megköveteli
(>= 0xFFFFFFFF méret/offszet), illetve data descriptor módban minden lokális
fejlécben (ez jelzi a 8 bájtos descriptor-mezőket).
"""

from __future__ import annotations

import struct
import unicodedata
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# --- ZIP szignatúrák és konstansok -----------------------------------------

_SIG_LOCAL = 0x04034B50
_SIG_DATA_DESCRIPTOR = 0x08074B50
_SIG_CENTRAL = 0x02014B50
_SIG_ZIP64_EOCD = 0x06064B50
_SIG_ZIP64_LOCATOR = 0x07064B50
_SIG_EOCD = 0x06054B50

_UINT32_MAX = 0xFFFFFFFF
_UINT16_MAX = 0xFFFF

#: 4.5-ös spec-verzió: ZIP64 támogatás szükséges.
_VERSION_ZIP64 = 45
#: "version made by": Unix host (3) + 4.5 spec.
_VERSION_MADE_BY = (3 << 8) | _VERSION_ZIP64

#: General purpose bit flag bitjei.
_FLAG_DATA_DESCRIPTOR = 0x0008
_FLAG_UTF8 = 0x0800

_LOCAL_HEADER_FIXED = 30
_CENTRAL_HEADER_FIXED = 46
_ZIP64_LFH_EXTRA_LEN = 20  # 2 (id) + 2 (len) + 8 + 8
_ZIP64_DD_LEN = 24  # signature + crc32 + 8 + 8
_ZIP64_EOCD_LEN = 56
_ZIP64_LOCATOR_LEN = 20
_EOCD_LEN = 22

#: Az egyes bejegyzések maximális (UTF-8 bájtban mért) neve.
MAX_NAME_BYTES = 200


class ZipWriteMode(StrEnum):
    DATA_DESCRIPTOR = "data_descriptor"
    CRC_IN_HEADER = "crc_in_header"


class ArchiveIntegrityError(RuntimeError):
    """A csomagolás közben derült ki, hogy a forrás nem az, aminek hittük."""


# --- Fájlnév-fertőtlenítés --------------------------------------------------

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
#: Windows/POSIX szempontból tiltott vagy félrevezető karakterek.
_FORBIDDEN_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(0x20)} | {"\x7f"}


def sanitize_component(name: str, *, fallback: str = "fajl") -> str:
    """Egyetlen útvonal-komponens biztonságossá tétele.

    Kezeli: path traversal (``..``), útvonal-elválasztók, Windows-tiltott
    karakterek, vezérlőkarakterek, Unicode formátum-karakterek (pl. a
    kiterjesztés-hamisító U+202E RIGHT-TO-LEFT OVERRIDE), Windows-foglalt nevek,
    záró pont/szóköz, üres név, túl hosszú név (UTF-8 bájtban, kiterjesztés
    megtartásával). A nevet NFC-re normalizálja, de a Unicode-ot megtartja.
    """
    if not name:
        return fallback
    name = unicodedata.normalize("NFC", name)
    # Unicode Cf (format) karakterek eltávolítása: BOM, zero-width, bidi override.
    name = "".join(ch for ch in name if unicodedata.category(ch) != "Cf")
    name = "".join("_" if ch in _FORBIDDEN_CHARS else ch for ch in name)
    name = name.strip()
    # Windows a záró pontot/szóközt levágja -> előre normalizáljuk.
    name = name.rstrip(". ")
    if not name or set(name) <= {"."}:
        return fallback
    stem, dot, _ext = name.rpartition(".")
    if (dot and stem and stem.upper() in _WINDOWS_RESERVED) or name.upper() in _WINDOWS_RESERVED:
        name = f"_{name}"
    return _truncate_utf8(name, MAX_NAME_BYTES, fallback=fallback)


def _truncate_utf8(name: str, limit: int, *, fallback: str) -> str:
    """UTF-8 bájtban korlátoz, a kiterjesztést megtartva, kódpont határon vágva."""
    if len(name.encode("utf-8")) <= limit:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot or len(ext.encode("utf-8")) > 16:
        stem, ext, dot = name, "", ""
    suffix = (f".{ext}" if dot else "")
    budget = limit - len(suffix.encode("utf-8"))
    if budget <= 0:
        return _truncate_utf8(fallback + suffix, limit, fallback=fallback) if suffix else fallback
    encoded = stem.encode("utf-8")[:budget]
    # Csonka többbájtos szekvencia levágása.
    while encoded and (encoded[-1] & 0xC0) == 0x80:
        encoded = encoded[:-1]
    stem = encoded.decode("utf-8", "ignore")
    return (stem or fallback) + suffix


def sanitize_arcpath(parts: Iterable[str]) -> str:
    """Több komponensből biztonságos, ZIP-en belüli útvonalat épít (mindig ``/``)."""
    clean = [sanitize_component(part, fallback="mappa") for part in parts if part is not None]
    clean = [c for c in clean if c]
    return "/".join(clean) if clean else "fajl"


class ArcNameAllocator:
    """Egyedi neveket oszt az archívumon belül.

    Kis- és nagybetűt nem különböztet meg (Windows/macOS kiterjesztés esetén
    ütköznének), az ismétlődéseket ``név (2).kiterjesztés`` alakban oldja fel.
    """

    def __init__(self) -> None:
        self._taken: set[str] = set()

    def allocate(self, path: str) -> str:
        key = path.casefold()
        if key not in self._taken:
            self._taken.add(key)
            return path
        directory, _, base = path.rpartition("/")
        prefix = f"{directory}/" if directory else ""
        stem, dot, ext = base.rpartition(".")
        if not dot:
            stem, ext = base, ""
        suffix = f".{ext}" if dot else ""
        counter = 2
        while True:
            candidate = f"{prefix}{stem} ({counter}){suffix}"
            candidate_key = candidate.casefold()
            if candidate_key not in self._taken:
                self._taken.add(candidate_key)
                return candidate
            counter += 1


# --- Bejegyzés-terv és méretbecslés ----------------------------------------


@dataclass(frozen=True, slots=True)
class PlannedEntry:
    """Egy tervezett archívum-bejegyzés (a méret előre ismert: STORE mód)."""

    arcname: str
    size: int
    modified: datetime


@dataclass(slots=True)
class WrittenEntry:
    """Egy ténylegesen kiírt bejegyzés."""

    arcname: str
    size: int
    crc32: int
    local_header_offset: int
    #: A lokális fejlécbe írt DOS dátum/idő - a központi könyvtár ugyanezt ismétli.
    dos_date: int = 0
    dos_time: int = 0


def _dos_datetime(value: datetime) -> tuple[int, int]:
    year = max(value.year, 1980)
    dosdate = ((year - 1980) << 9) | (value.month << 5) | value.day
    dostime = (value.hour << 11) | (value.minute << 5) | (value.second // 2)
    return dosdate, dostime


def predict_archive_size(
    entries: Iterable[PlannedEntry], *, mode: ZipWriteMode = ZipWriteMode.DATA_DESCRIPTOR
) -> int:
    """A végleges archívum bájtszáma. STORE módban ez pontos, nem becslés."""
    offset = 0
    central = 0
    count = 0
    for count, entry in enumerate(entries, start=1):
        name_len = len(entry.arcname.encode("utf-8"))
        needs_zip64 = entry.size >= _UINT32_MAX
        if mode is ZipWriteMode.DATA_DESCRIPTOR:
            local_extra = _ZIP64_LFH_EXTRA_LEN
            trailer = _ZIP64_DD_LEN
        else:
            local_extra = _ZIP64_LFH_EXTRA_LEN if needs_zip64 else 0
            trailer = 0
        local_offset = offset
        offset += _LOCAL_HEADER_FIXED + name_len + local_extra + entry.size + trailer
        central += _CENTRAL_HEADER_FIXED + name_len + _central_zip64_extra_len(
            entry.size, local_offset
        )
    return offset + central + _ZIP64_EOCD_LEN + _ZIP64_LOCATOR_LEN + _EOCD_LEN


def _central_zip64_extra_len(size: int, local_header_offset: int) -> int:
    fields = 0
    if size >= _UINT32_MAX:
        fields += 2  # uncompressed + compressed
    if local_header_offset >= _UINT32_MAX:
        fields += 1
    return 4 + 8 * fields if fields else 0


# --- Az író -----------------------------------------------------------------


@dataclass(slots=True)
class _Sink:
    """Bájtszámláló burkolat egy csak-írható kimenet fölé."""

    target: object
    written: int = 0

    def write(self, data: bytes) -> None:
        if not data:
            return
        self.target.write(data)
        self.written += len(data)


class Zip64Writer:
    """Streamelt ZIP64 (STORE) archívumíró.

    Használat::

        writer = Zip64Writer(sink)
        writer.add_stream(PlannedEntry(...), chunks)
        writer.close()
    """

    def __init__(
        self,
        sink,
        *,
        mode: ZipWriteMode = ZipWriteMode.DATA_DESCRIPTOR,
        on_progress=None,
    ) -> None:
        self._sink = _Sink(sink)
        self._mode = mode
        self._entries: list[WrittenEntry] = []
        self._closed = False
        self._on_progress = on_progress

    @property
    def bytes_written(self) -> int:
        return self._sink.written

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    # -- bejegyzés hozzáadása ------------------------------------------------

    def add_stream(self, entry: PlannedEntry, chunks: Iterator[bytes], *, crc32: int | None = None) -> WrittenEntry:
        """Egy fájl hozzáadása streamelve.

        ``crc32``: ``CRC_IN_HEADER`` módban kötelező (előre kiszámított érték).
        A ténylegesen beolvasott bájtszámot összeveti ``entry.size``-zal, és
        eltérés esetén ``ArchiveIntegrityError``-t dob - a forrás menet közbeni
        változása így soha nem tűnik sikeres exportnak.
        """
        if self._closed:
            raise RuntimeError("Az archívum már le van zárva.")
        name = entry.arcname.encode("utf-8")
        local_offset = self._sink.written
        use_dd = self._mode is ZipWriteMode.DATA_DESCRIPTOR
        if not use_dd and crc32 is None:
            raise ValueError("CRC_IN_HEADER módban a crc32 kötelező.")

        needs_zip64 = entry.size >= _UINT32_MAX
        dosdate, dostime = _dos_datetime(entry.modified)
        flags = _FLAG_UTF8 | (_FLAG_DATA_DESCRIPTOR if use_dd else 0)

        if use_dd:
            header_crc = 0
            header_size = 0
            extra = struct.pack("<HHQQ", 0x0001, 16, 0, 0)
        else:
            header_crc = crc32 & 0xFFFFFFFF
            if needs_zip64:
                header_size = _UINT32_MAX
                extra = struct.pack("<HHQQ", 0x0001, 16, entry.size, entry.size)
            else:
                header_size = entry.size
                extra = b""

        self._sink.write(
            struct.pack(
                "<IHHHHHIIIHH",
                _SIG_LOCAL,
                _VERSION_ZIP64,
                flags,
                0,  # STORE
                dostime,
                dosdate,
                header_crc,
                header_size,
                header_size,
                len(name),
                len(extra),
            )
        )
        self._sink.write(name)
        if extra:
            self._sink.write(extra)

        running_crc = 0
        payload = 0
        for chunk in chunks:
            if not chunk:
                continue
            payload += len(chunk)
            if payload > entry.size:
                raise ArchiveIntegrityError(
                    f"A forrás megnőtt csomagolás közben: {entry.arcname!r} "
                    f"(várt {entry.size} bájt, már {payload} bájt érkezett)"
                )
            running_crc = zlib.crc32(chunk, running_crc)
            self._sink.write(chunk)
            if self._on_progress is not None:
                self._on_progress(len(chunk))
        if payload != entry.size:
            raise ArchiveIntegrityError(
                f"A forrás lerövidült csomagolás közben: {entry.arcname!r} "
                f"(várt {entry.size} bájt, kapott {payload} bájt)"
            )
        if crc32 is not None and (crc32 & 0xFFFFFFFF) != running_crc:
            raise ArchiveIntegrityError(
                f"A forrás tartalma megváltozott csomagolás közben: {entry.arcname!r} "
                f"(CRC32 {crc32:08x} -> {running_crc:08x})"
            )

        if use_dd:
            self._sink.write(
                struct.pack("<IIQQ", _SIG_DATA_DESCRIPTOR, running_crc, entry.size, entry.size)
            )

        written = WrittenEntry(
            arcname=entry.arcname, size=entry.size, crc32=running_crc,
            local_header_offset=local_offset, dos_date=dosdate, dos_time=dostime,
        )
        self._entries.append(written)
        return written

    # -- lezárás -------------------------------------------------------------

    def close(self) -> int:
        """Központi könyvtár + ZIP64 EOCD kiírása. A teljes bájtszámot adja."""
        if self._closed:
            return self._sink.written
        self._closed = True
        cd_offset = self._sink.written
        for entry in self._entries:
            self._write_central_header(entry)
        cd_size = self._sink.written - cd_offset
        self._write_zip64_eocd(cd_offset, cd_size)
        return self._sink.written

    def _write_central_header(self, entry: WrittenEntry) -> None:
        name = entry.arcname.encode("utf-8")
        dosdate, dostime = entry.dos_date, entry.dos_time
        size_field = entry.size
        offset_field = entry.local_header_offset
        zip64_values: list[int] = []
        if entry.size >= _UINT32_MAX:
            zip64_values.extend([entry.size, entry.size])
            size_field = _UINT32_MAX
        if entry.local_header_offset >= _UINT32_MAX:
            zip64_values.append(entry.local_header_offset)
            offset_field = _UINT32_MAX
        if zip64_values:
            extra = struct.pack("<HH", 0x0001, 8 * len(zip64_values)) + b"".join(
                struct.pack("<Q", value) for value in zip64_values
            )
        else:
            extra = b""

        flags = _FLAG_UTF8 | (
            _FLAG_DATA_DESCRIPTOR if self._mode is ZipWriteMode.DATA_DESCRIPTOR else 0
        )
        self._sink.write(
            struct.pack(
                "<IHHHHHHIIIHHHHHII",
                _SIG_CENTRAL,
                _VERSION_MADE_BY,
                _VERSION_ZIP64,
                flags,
                0,  # STORE
                dostime,
                dosdate,
                entry.crc32,
                size_field,
                size_field,
                len(name),
                len(extra),
                0,  # file comment length
                0,  # disk number start
                0,  # internal attributes
                0o644 << 16,  # external attributes (Unix rw-r--r--)
                offset_field,
            )
        )
        self._sink.write(name)
        if extra:
            self._sink.write(extra)

    def _write_zip64_eocd(self, cd_offset: int, cd_size: int) -> None:
        count = len(self._entries)
        zip64_eocd_offset = self._sink.written
        self._sink.write(
            struct.pack(
                "<IQHHIIQQQQ",
                _SIG_ZIP64_EOCD,
                _ZIP64_EOCD_LEN - 12,  # a rekord mérete a mezőtől számítva
                _VERSION_MADE_BY,
                _VERSION_ZIP64,
                0,  # this disk
                0,  # disk with CD
                count,
                count,
                cd_size,
                cd_offset,
            )
        )
        self._sink.write(
            struct.pack("<IIQI", _SIG_ZIP64_LOCATOR, 0, zip64_eocd_offset, 1)
        )
        self._sink.write(
            struct.pack(
                "<IHHHHIIH",
                _SIG_EOCD,
                0,
                0,
                min(count, _UINT16_MAX),
                min(count, _UINT16_MAX),
                min(cd_size, _UINT32_MAX),
                min(cd_offset, _UINT32_MAX),
                0,
            )
        )


__all__ = [
    "MAX_NAME_BYTES",
    "ArcNameAllocator",
    "ArchiveIntegrityError",
    "PlannedEntry",
    "WrittenEntry",
    "Zip64Writer",
    "ZipWriteMode",
    "predict_archive_size",
    "sanitize_arcpath",
    "sanitize_component",
]
