"""ZIP64 író: formátum-helyesség független olvasókkal, méret-előrejelzés, névkezelés."""

from __future__ import annotations

import io
import os
import struct
import subprocess
import zipfile
import zlib
from datetime import UTC, datetime

import pytest

from app.services.zip64 import (
    ArchiveIntegrityError,
    ArcNameAllocator,
    PlannedEntry,
    Zip64Writer,
    ZipWriteMode,
    predict_archive_size,
    sanitize_arcpath,
    sanitize_component,
)

MODIFIED = datetime(2026, 9, 8, 10, 30, 0, tzinfo=UTC)


class WriteOnly:
    """Csak write() - bizonyítja, hogy az író nem seekel."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, data: bytes) -> int:
        return self.buffer.write(data)


def _chunks(data: bytes, size: int = 7):
    return (data[i:i + size] for i in range(0, len(data), size))


def _build(files: dict[str, bytes], mode: ZipWriteMode) -> tuple[bytes, int]:
    sink = WriteOnly()
    writer = Zip64Writer(sink, mode=mode)
    planned = [PlannedEntry(name, len(data), MODIFIED) for name, data in files.items()]
    for entry, data in zip(planned, files.values()):
        crc = zlib.crc32(data) if mode is ZipWriteMode.CRC_IN_HEADER else None
        writer.add_stream(entry, _chunks(data), crc32=crc)
    writer.close()
    return sink.buffer.getvalue(), predict_archive_size(planned, mode=mode)


SAMPLE = {
    "a.txt": b"hello world" * 100,
    "mappa/ékezetes árvíztűrő.txt": "tükörfúrógép\n".encode() * 50,
    "mappa/日本語ファイル.bin": os.urandom(4096),
    "üres.bin": b"",
}


@pytest.mark.parametrize("mode", list(ZipWriteMode))
def test_roundtrip_python_zipfile_and_unzip(mode: ZipWriteMode, tmp_path):
    blob, predicted = _build(SAMPLE, mode)
    assert len(blob) == predicted, "STORE módban a méret bájtra pontosan előre számítható"

    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        assert zf.testzip() is None
        assert zf.namelist() == list(SAMPLE)
        for name, data in SAMPLE.items():
            info = zf.getinfo(name)
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.flag_bits & 0x800, "UTF-8 név-flag"
            assert zf.read(name) == data

    path = tmp_path / f"{mode.value}.zip"
    path.write_bytes(blob)
    result = subprocess.run(["unzip", "-t", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No errors detected" in result.stdout


def test_zip64_end_records_present():
    blob, _ = _build(SAMPLE, ZipWriteMode.DATA_DESCRIPTOR)
    assert struct.pack("<I", 0x06064B50) in blob, "ZIP64 EOCD rekord"
    assert struct.pack("<I", 0x07064B50) in blob, "ZIP64 EOCD locator"
    assert blob.endswith(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 4, 4,
                                     *struct.unpack("<II", blob[-10:-2]), 0))


def test_deterministic_output():
    first, _ = _build(SAMPLE, ZipWriteMode.DATA_DESCRIPTOR)
    second, _ = _build(SAMPLE, ZipWriteMode.DATA_DESCRIPTOR)
    assert first == second, "Ugyanaz a bemenet ugyanazt a bájtsorozatot adja (stabil hash/ETag)"


def test_more_than_65535_entries_uses_zip64_counts(tmp_path):
    """A ZIP64 egyik kiváltó oka: 65535-nél több bejegyzés."""
    count = 70_000
    sink = WriteOnly()
    writer = Zip64Writer(sink, mode=ZipWriteMode.DATA_DESCRIPTOR)
    for index in range(count):
        writer.add_stream(PlannedEntry(f"d/{index:06d}.txt", 1, MODIFIED), iter([b"x"]))
    writer.close()
    blob = sink.buffer.getvalue()
    # A klasszikus EOCD-ben 0xFFFF a darabszám, a ZIP64 EOCD-ben a valódi.
    eocd = blob[-22:]
    _, _, _, on_disk, total, _, _, _ = struct.unpack("<IHHHHIIH", eocd)
    assert on_disk == total == 0xFFFF
    z64_pos = blob.rfind(struct.pack("<I", 0x06064B50))
    (_, _, _, _, _, _, entries_disk, entries_total, _, _) = struct.unpack("<IQHHIIQQQQ", blob[z64_pos:z64_pos + 56])
    assert entries_disk == entries_total == count
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        assert len(zf.namelist()) == count
        assert zf.read("d/069999.txt") == b"x"
    path = tmp_path / "many.zip"
    path.write_bytes(blob)
    result = subprocess.run(["unzip", "-t", "-q", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_source_shrunk_is_integrity_error():
    writer = Zip64Writer(WriteOnly())
    with pytest.raises(ArchiveIntegrityError, match="lerövidült"):
        writer.add_stream(PlannedEntry("x.bin", 10, MODIFIED), iter([b"abc"]))


def test_source_grew_is_integrity_error():
    writer = Zip64Writer(WriteOnly())
    with pytest.raises(ArchiveIntegrityError, match="megnőtt"):
        writer.add_stream(PlannedEntry("x.bin", 2, MODIFIED), iter([b"abc"]))


def test_crc_mismatch_is_integrity_error():
    writer = Zip64Writer(WriteOnly(), mode=ZipWriteMode.CRC_IN_HEADER)
    with pytest.raises(ArchiveIntegrityError, match="tartalma megváltozott"):
        writer.add_stream(PlannedEntry("x.bin", 3, MODIFIED), iter([b"abc"]), crc32=zlib.crc32(b"abd"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", ".._.._etc_passwd"),
        ("..", "fajl"),
        (".", "fajl"),
        ("", "fajl"),
        ("C:\\Users\\x\\kép.jpg", "C__Users_x_kép.jpg"),
        ("CON.txt", "_CON.txt"),
        ("lpt1", "_lpt1"),
        ("trailing dots...", "trailing dots"),
        ("  szóköz  ", "szóköz"),
        ("bad<>:\"|?*chars.jpg", "bad_______chars.jpg"),
        ("ctrl\x00\x1fchars.jpg", "ctrl__chars.jpg"),
        ("kép\u202egnp.exe", "képgnp.exe"),  # RTL override eltávolítva
        ("árvíztűrő tükörfúrógép.JPG", "árvíztűrő tükörfúrógép.JPG"),
        ("日本語ファイル.png", "日本語ファイル.png"),
    ],
)
def test_sanitize_component(raw: str, expected: str):
    assert sanitize_component(raw) == expected


def test_sanitize_component_truncates_utf8_bytes_keeping_extension():
    name = "ő" * 300 + ".jpeg"
    result = sanitize_component(name)
    assert len(result.encode("utf-8")) <= 200
    assert result.endswith(".jpeg")
    result.encode("utf-8")  # érvényes UTF-8 (nincs csonka kódpont)


def test_sanitize_arcpath_never_traverses():
    assert sanitize_arcpath(["../x", "..", "a/b", "c.jpg"]) == ".._x/fajl/a_b/c.jpg".replace("fajl", "mappa")


def test_arcname_allocator_dedupes_case_insensitively():
    allocator = ArcNameAllocator()
    assert allocator.allocate("m/kép.jpg") == "m/kép.jpg"
    assert allocator.allocate("m/KÉP.JPG") == "m/KÉP (2).JPG"
    assert allocator.allocate("m/kép.jpg") == "m/kép (3).jpg"
    assert allocator.allocate("nincs-kiterjesztes") == "nincs-kiterjesztes"
    assert allocator.allocate("nincs-kiterjesztes") == "nincs-kiterjesztes (2)"
