#!/usr/bin/env python3
"""Reprodukálható nagy-galéria (akár 50 GB) export + letöltés mérőharness.

Mit csinál (minden lépés VALÓDI bájtokkal, nem mockkal, nem sparse fájllal):

1. Előellenőrzés: szabad lemezhely és korlátok. Ha nincs elég hely, a futás
   *NEM TESZTELT* eredménnyel, egyértelmű indoklással áll le (exit 3).
2. Szintetikus bemenet: pontosan ``--total-bytes`` bájtnyi fájl a privát
   objektumtárban (``os.urandom``, ténylegesen lemezre írva), fájlonként sha256.
3. Export: a job a valódi HTTP API-n jön létre, a csomagot a valódi worker
   (``python -m app.worker --once``) készíti **külön processzben**, így a
   csúcsmemóriája (RSS high-water mark) függetlenül mérhető.
4. Letöltés a valódi, Range-képes HTTP végponton: szándékos megszakítás,
   link-megújítás, folytatás ``Range`` + ``If-Range`` fejléccel; a letöltött
   bájtfolyam sha256-ja menet közben számolva (nem tároljuk másodszor).
5. ZIP64 ellenőrzés (zip64 EOCD/locator, >4 GiB méret/offszet extra mezők),
   független olvasók (``unzip -t``, Python ``zipfile``), majd **minden**
   bejegyzés kicsomagolás közbeni sha256-ja == a forrás sha256-a.
6. Jegyzőkönyv: JSON + Markdown (idő, bájtszámok, csúcsmemória, ellenőrzések).

Példa (50 GB - ~101 GB szabad hely kell):

    cd backend && .venv/bin/python scripts/bench_gallery_export.py \
        --total-bytes 50000000000 --file-count 500 --big-file-bytes 4500000000 \
        --work-dir /mnt/bench --report-dir ../docs/gallery-export-evidence --label 50gb

Kisebb, ZIP64-et még mindig kiváltó futás (>4 GiB, ~11 GB szabad hely):

    .venv/bin/python scripts/bench_gallery_export.py --total-bytes 5000000000 \
        --file-count 40 --big-file-bytes 4500000000 --label 5gb
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import platform
import resource
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse
import zipfile
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

CHUNK = 8 * 1024 * 1024
UINT32_MAX = 0xFFFFFFFF


def log(message: str) -> None:
    print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {message}", flush=True)


def human(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while value >= 1000 and index < len(units) - 1:
        value /= 1000
        index += 1
    return f"{value:.2f} {units[index]}"


# --- 1. előellenőrzés -----------------------------------------------------------


def preflight(work_dir: Path, total_bytes: int, report: dict) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(work_dir)
    # forrás + archívum (STORE: ~azonos méret) + biztonsági sáv
    needed = 2 * total_bytes + 1_000_000_000
    mem = _meminfo()
    report["preflight"] = {
        "work_dir": str(work_dir),
        "disk_total_bytes": usage.total,
        "disk_free_bytes": usage.free,
        "disk_needed_bytes": needed,
        "mem_total_bytes": mem.get("MemTotal"),
        "mem_available_bytes": mem.get("MemAvailable"),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "kernel": platform.release(),
    }
    log(f"Szabad lemezhely: {human(usage.free)}, szükséges: {human(needed)} "
        f"(forrás {human(total_bytes)} + archívum {human(total_bytes)} + 1 GB sáv)")
    if usage.free < needed:
        report["verdict"] = "NEM TESZTELT"
        report["blocker"] = (
            f"Nincs elég szabad lemezhely: {usage.free} bájt szabad, {needed} bájt szükséges "
            f"({human(usage.free)} < {human(needed)})."
        )
        log("NEM TESZTELT: " + report["blocker"])
        _write_report(report)
        sys.exit(3)


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            out[key] = int(rest.split()[0]) * 1024
    except OSError:
        pass
    return out


# --- 2. szintetikus bemenet -----------------------------------------------------


def generate_sources(storage_root: Path, project_id: int, total_bytes: int, file_count: int,
                     big_file_bytes: int, prefix: str) -> list[dict]:
    """Pontosan ``total_bytes`` bájt, valódi (os.urandom) tartalommal, fájlonként sha256."""
    sizes: list[int] = []
    remaining = total_bytes
    if big_file_bytes and big_file_bytes < total_bytes and file_count > 1:
        sizes.append(big_file_bytes)
        remaining -= big_file_bytes
        small_count = file_count - 1
    else:
        small_count = file_count
    base = remaining // small_count
    for index in range(small_count):
        sizes.append(base + (remaining - base * small_count if index == small_count - 1 else 0))
    assert sum(sizes) == total_bytes, (sum(sizes), total_bytes)

    files = []
    written_total = 0
    started = time.monotonic()
    for index, size in enumerate(sizes):
        key = f"{prefix}{project_id}/bench-{index:05d}.bin"
        path = storage_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with path.open("wb", buffering=CHUNK) as fh:
            left = size
            while left > 0:
                block = os.urandom(min(CHUNK, left))
                fh.write(block)
                digest.update(block)
                left -= len(block)
            fh.flush()
            os.fsync(fh.fileno())
        actual = path.stat().st_size
        assert actual == size, (actual, size)
        blocks = os.stat(path).st_blocks * 512
        files.append({"key": key, "title": f"Forgatás {index:05d}", "size": size,
                      "sha256": digest.hexdigest(), "allocated_bytes": blocks})
        written_total += size
        if index % max(1, len(sizes) // 10) == 0 or index == len(sizes) - 1:
            elapsed = time.monotonic() - started
            log(f"  forrás {index + 1}/{len(sizes)}: {human(written_total)} "
                f"({human(written_total / max(elapsed, 1e-6))}/s)")
    return files


# --- segédek --------------------------------------------------------------------


class Proc:
    """Alfolyamat, amelynek csúcs-RSS-ét (VmHWM) is kiolvassuk."""

    def __init__(self, args: list[str], env: dict, log_path: Path) -> None:
        self.log_file = log_path.open("ab")
        self.proc = subprocess.Popen(args, env=env, stdout=self.log_file, stderr=subprocess.STDOUT,
                                     cwd=str(BACKEND_DIR))
        self.peak_rss = 0

    def sample(self) -> None:
        try:
            for line in Path(f"/proc/{self.proc.pid}/status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    self.peak_rss = max(self.peak_rss, int(line.split()[1]) * 1024)
        except OSError:
            pass

    def stop(self) -> None:
        self.sample()
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log_file.close()


def wait_http(host: str, port: int, path: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", path)
            if conn.getresponse().status < 500:
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"A szolgáltatás nem indult el: {host}:{port}{path}")


def api(host: str, port: int, method: str, path: str, token: str | None = None, body: bytes | None = None,
        headers: dict | None = None) -> tuple[int, dict, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=600)
    hdrs = dict(headers or {})
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    conn.request(method, path, body=body, headers=hdrs)
    response = conn.getresponse()
    data = response.read()
    return response.status, dict(response.getheaders()), data


# --- 4. letöltés Range-folytatással ---------------------------------------------


def download_with_interruption(host: str, port: int, public_id: str, token: str, size: int,
                               cut_at: int, report: dict) -> str:
    """Letöltés: megszakítás ``cut_at`` bájtnál, új link, folytatás Range-dzsel.

    A bájtfolyamot nem tároljuk, csak sha256-oljuk (a lemezhely miatt); a
    végső hash a szerver által közölt archive_sha256-tal egyezik-e = bizonyíték.
    """
    digest = hashlib.sha256()
    received = 0
    started = time.monotonic()

    def ticket() -> dict:
        status, _, data = api(host, port, "POST", f"/api/v1/gallery-exports/{public_id}/download-url", token)
        assert status == 200, (status, data[:300])
        return json.loads(data)

    first = ticket()
    url = urllib.parse.urlsplit(first["url"])
    conn = http.client.HTTPConnection(host, port, timeout=600)
    conn.request("GET", f"{url.path}?{url.query}")
    response = conn.getresponse()
    assert response.status == 200, response.status
    assert int(response.getheader("Content-Length")) == size
    assert response.getheader("Accept-Ranges") == "bytes"
    etag = response.getheader("ETag")
    disposition = response.getheader("Content-Disposition")
    while received < cut_at:
        block = response.read(min(CHUNK, cut_at - received))
        if not block:
            break
        digest.update(block)
        received += len(block)
    conn.close()  # szándékos megszakítás
    log(f"  letöltés megszakítva {human(received)}-nál, új link kérése és folytatás Range-dzsel")

    second = ticket()
    assert second["etag"] == first["etag"] and second["size"] == first["size"], "az objektum nem változhat"
    url = urllib.parse.urlsplit(second["url"])
    conn = http.client.HTTPConnection(host, port, timeout=600)
    conn.request("GET", f"{url.path}?{url.query}", headers={"Range": f"bytes={received}-", "If-Range": etag})
    response = conn.getresponse()
    assert response.status == 206, response.status
    assert response.getheader("Content-Range") == f"bytes {received}-{size - 1}/{size}"
    assert response.getheader("ETag") == etag
    assert int(response.getheader("Content-Length")) == size - received
    resumed_from = received
    while True:
        block = response.read(CHUNK)
        if not block:
            break
        digest.update(block)
        received += len(block)
    conn.close()
    elapsed = time.monotonic() - started
    report["download"] = {
        "bytes_received": received,
        "content_length": size,
        "interrupted_at": resumed_from,
        "resumed_with_range": True,
        "etag_stable_across_renewal": True,
        "content_disposition": disposition,
        "seconds": round(elapsed, 3),
        "throughput_bytes_per_s": int(received / max(elapsed, 1e-6)),
        "sha256": digest.hexdigest(),
    }
    assert received == size, (received, size)
    return digest.hexdigest()


# --- 5. ZIP64 + integritás -------------------------------------------------------


def verify_archive(archive_path: Path, files: list[dict], report: dict) -> None:
    started = time.monotonic()
    size = archive_path.stat().st_size
    with archive_path.open("rb") as fh:
        fh.seek(max(size - 65536, 0))
        tail = fh.read()
    zip64_eocd = struct.pack("<I", 0x06064B50) in tail
    zip64_locator = struct.pack("<I", 0x07064B50) in tail
    z64 = tail.rfind(struct.pack("<I", 0x06064B50))
    z64_fields = struct.unpack("<IQHHIIQQQQ", tail[z64:z64 + 56]) if z64 >= 0 else None
    eocd = struct.unpack("<IHHHHIIH", tail[-22:])

    with zipfile.ZipFile(archive_path) as zf:
        infos = zf.infolist()
        entries_over_4g = [i for i in infos if i.file_size >= UINT32_MAX]
        offsets_over_4g = [i for i in infos if i.header_offset >= UINT32_MAX]
        # zip64 extra a >4 GiB bejegyzéseknél a központi könyvtárban
        def has_zip64_extra(info: zipfile.ZipInfo) -> bool:
            extra = info.extra
            while len(extra) >= 4:
                tag, length = struct.unpack("<HH", extra[:4])
                if tag == 0x0001:
                    return True
                extra = extra[4 + length:]
            return False
        zip64_extra_ok = all(has_zip64_extra(i) for i in entries_over_4g + offsets_over_4g)
        stored_only = all(i.compress_type == zipfile.ZIP_STORED for i in infos)

        # minden bejegyzés kicsomagolás közbeni sha256-a (memóriában csak egy chunk)
        expected = {Path(f["key"]).name: f for f in files}
        by_title = {f["title"]: f for f in files}
        verified = 0
        mismatches = []
        for info in infos:
            digest = hashlib.sha256()
            with zf.open(info) as src:
                while True:
                    block = src.read(CHUNK)
                    if not block:
                        break
                    digest.update(block)
            title = info.filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            source = by_title.get(title) or expected.get(info.filename)
            if source is None or digest.hexdigest() != source["sha256"] or info.file_size != source["size"]:
                mismatches.append(info.filename)
            else:
                verified += 1

    unzip = subprocess.run(["unzip", "-t", "-q", str(archive_path)], capture_output=True, text=True, check=False)
    report["verification"] = {
        "archive_bytes": size,
        "entries": len(infos),
        "all_entries_stored": stored_only,
        "zip64_eocd_present": zip64_eocd,
        "zip64_locator_present": zip64_locator,
        "zip64_eocd_entries": z64_fields[7] if z64_fields else None,
        "zip64_eocd_cd_offset": z64_fields[9] if z64_fields else None,
        "classic_eocd_cd_offset_saturated": eocd[6] == UINT32_MAX,
        "entries_over_4gib": len(entries_over_4g),
        "entries_with_offset_over_4gib": len(offsets_over_4g),
        "zip64_extra_present_where_required": zip64_extra_ok,
        "python_zipfile_testzip": "ok",
        "unzip_t_returncode": unzip.returncode,
        "unzip_t_output": (unzip.stdout + unzip.stderr).strip()[-300:],
        "entries_hash_verified": verified,
        "entries_hash_mismatch": mismatches[:20],
        "seconds": round(time.monotonic() - started, 3),
    }
    assert not mismatches, mismatches[:5]
    assert verified == len(files) == len(infos)
    assert unzip.returncode == 0, unzip.stdout + unzip.stderr


# --- jegyzőkönyv ----------------------------------------------------------------


def _write_report(report: dict) -> None:
    out_dir = Path(report["report_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    label = report["label"]
    (out_dir / f"bench-{label}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    (out_dir / f"bench-{label}.md").write_text(_markdown(report))
    log(f"Jegyzőkönyv: {out_dir / f'bench-{label}.md'}")


def _markdown(r: dict) -> str:
    p = r.get("preflight", {})
    lines = [
        f"# Galéria-export mérési jegyzőkönyv - `{r['label']}`",
        "",
        f"- Időpont (UTC): {r['started_at']}",
        f"- **Eredmény: {r.get('verdict', 'FUTÁS KÖZBEN')}**",
        (f"- Cél összméret: **{r['params']['total_bytes']:,} bájt** ({human(r['params']['total_bytes'])}), "
        f"fájlok: {r['params']['file_count']}, legnagyobb fájl: {r['params']['big_file_bytes']:,} bájt"),
        f"- Parancs: `{r['command']}`",
        "",
        "## Környezet és előellenőrzés",
        (f"- Szabad lemezhely: {p.get('disk_free_bytes', 0):,} bájt ({human(p.get('disk_free_bytes', 0))}); "
        f"szükséges: {p.get('disk_needed_bytes', 0):,} bájt ({human(p.get('disk_needed_bytes', 0))})"),
        (f"- Memória: {human(p.get('mem_total_bytes') or 0)} összes, CPU: {p.get('cpu_count')}, "
        f"Python {p.get('python')}, kernel {p.get('kernel')}"),
    ]
    if r.get("blocker"):
        lines += ["", "## Akadály", "", r["blocker"], "",
                  "Ez a futás **NEM TESZTELT**: a fenti parancs elegendő lemezhellyel újrafuttatható."]
        return "\n".join(lines) + "\n"
    g = r.get("generation", {})
    e = r.get("export", {})
    d = r.get("download", {})
    v = r.get("verification", {})
    lines += [
        "",
        "## Bemenet (valódi bájtok, nem sparse)",
        (f"- Kiírt forrásbájt: **{g.get('bytes_written', 0):,}** ({human(g.get('bytes_written', 0))}), "
        f"lefoglalt blokk: {g.get('bytes_allocated', 0):,} bájt, idő: {g.get('seconds')} s "
        f"({human(g.get('throughput_bytes_per_s', 0))}/s)"),
        "",
        "## Export (külön worker-processz)",
        (f"- Állapot: **{e.get('status')}**, fájlok: {e.get('files')}, csomag: **{e.get('archive_bytes', 0):,} bájt**"
        f" ({human(e.get('archive_bytes', 0))}), várt: {e.get('expected_archive_bytes', 0):,} bájt "
        f"(egyezik: {e.get('size_matches_prediction')})"),
        f"- Idő: **{e.get('seconds')} s** ({human(e.get('throughput_bytes_per_s', 0))}/s)",
        (f"- **Worker csúcsmemória (RSS high-water): {e.get('worker_peak_rss_bytes', 0):,} bájt "
        f"({human(e.get('worker_peak_rss_bytes', 0))})**"),
        f"- sha256: `{e.get('archive_sha256')}`",
        "",
        "## Letöltés (valódi HTTP, Range-folytatás)",
        (f"- Megszakítva {d.get('interrupted_at', 0):,} bájtnál, link megújítva (ETag változatlan: "
        f"{d.get('etag_stable_across_renewal')}), folytatva `Range`+`If-Range` fejléccel (206)"),
        (f"- Fogadott bájt: **{d.get('bytes_received', 0):,}** / Content-Length {d.get('content_length', 0):,}, "
        f"idő: {d.get('seconds')} s ({human(d.get('throughput_bytes_per_s', 0))}/s)"),
        f"- Letöltött folyam sha256 == szerver archive_sha256: **{r.get('download_hash_matches')}**",
        (f"- API-processz csúcsmemória a letöltés alatt: {r.get('api_peak_rss_bytes', 0):,} bájt "
        f"({human(r.get('api_peak_rss_bytes', 0))})"),
        f"- Content-Disposition: `{d.get('content_disposition')}`",
        "",
        "## ZIP64 és integritás",
        (f"- ZIP64 EOCD rekord: {v.get('zip64_eocd_present')}, locator: {v.get('zip64_locator_present')}, "
        f"ZIP64 EOCD bejegyzésszám: {v.get('zip64_eocd_entries')}, CD offszet: {v.get('zip64_eocd_cd_offset')}"),
        f"- Klasszikus EOCD CD-offszet telített (0xFFFFFFFF): {v.get('classic_eocd_cd_offset_saturated')}",
        (f"- >4 GiB bejegyzés: {v.get('entries_over_4gib')}, >4 GiB offszetű bejegyzés: "
        f"{v.get('entries_with_offset_over_4gib')}, zip64 extra ott, ahol kell: "
        f"{v.get('zip64_extra_present_where_required')}"),
        f"- Minden bejegyzés STORE: {v.get('all_entries_stored')}",
        f"- `unzip -t` visszatérési kód: {v.get('unzip_t_returncode')} (`{v.get('unzip_t_output')}`)",
        (f"- **Kicsomagolt bejegyzések sha256 == forrás sha256: {v.get('entries_hash_verified')}/{v.get('entries')}**"
        f" (eltérés: {len(v.get('entries_hash_mismatch', []))}), idő: {v.get('seconds')} s"),
        "",
        f"Teljes futásidő: {r.get('total_seconds')} s",
    ]
    return "\n".join(lines) + "\n"


# --- fő folyamat ----------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--total-bytes", type=int, required=True, help="pl. 50000000000")
    parser.add_argument("--file-count", type=int, default=500)
    parser.add_argument("--big-file-bytes", type=int, default=4_500_000_000,
                        help="egy >4 GiB fájl a ZIP64 méretmezők kiváltásához (0 = nincs)")
    parser.add_argument("--work-dir", default=str(BACKEND_DIR / "var" / "bench"))
    parser.add_argument("--report-dir", default=str(BACKEND_DIR.parent / "docs" / "gallery-export-evidence"))
    parser.add_argument("--label", default=None)
    parser.add_argument("--api-port", type=int, default=18010)
    parser.add_argument("--keep", action="store_true", help="a munkakönyvtár megtartása a futás után")
    args = parser.parse_args()

    label = args.label or f"{args.total_bytes // 1_000_000_000}gb"
    work_dir = Path(args.work_dir).resolve() / label
    if work_dir.exists():
        shutil.rmtree(work_dir)
    report: dict = {
        "label": label,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": " ".join([Path(sys.argv[0]).name, *sys.argv[1:]]),
        "params": {"total_bytes": args.total_bytes, "file_count": args.file_count,
                   "big_file_bytes": args.big_file_bytes if args.big_file_bytes < args.total_bytes else 0},
        "report_dir": args.report_dir,
    }
    t0 = time.monotonic()
    preflight(work_dir, args.total_bytes, report)

    storage_root = work_dir / "storage"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{work_dir}/bench.db",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_ROOT": str(storage_root),
        "SECRET_KEY": "bench-secret-not-for-production",
        "EXPORT_PROGRESS_INTERVAL_SECONDS": "5",
        "EXPORT_DOWNLOAD_URL_TTL_SECONDS": "3600",
        "ENVIRONMENT": "bench",
        "PYTHONUNBUFFERED": "1",
    }
    for key, value in env.items():
        if key in ("DATABASE_URL", "STORAGE_BACKEND", "LOCAL_STORAGE_ROOT", "SECRET_KEY",
                   "EXPORT_PROGRESS_INTERVAL_SECONDS", "EXPORT_DOWNLOAD_URL_TTL_SECONDS", "ENVIRONMENT"):
            os.environ[key] = value

    from app.core.config import settings
    from app.core.database import SessionLocal, engine
    from app.core.security import create_access_token, hash_password
    from app.models import Base
    from app.models.client import Client
    from app.models.employee import Employee, EmployeeType, SystemRole
    from app.models.media import Media
    from app.models.project import Project
    from app.models.project_code import ProjectCode

    Base.metadata.create_all(engine)
    db = SessionLocal()
    client = Client(nev="Bench Kft")
    db.add(client); db.flush()
    code = ProjectCode(projektkod=f"BENCH-{label.upper()}", client_id=client.id)
    db.add(code); db.flush()
    project = Project(nev=f"Bench {label}", project_code_id=code.id)
    db.add(project); db.flush()
    admin = Employee(full_name="Bench admin", tipus=EmployeeType.BELSOS, email="bench@hype.test",
                     role=SystemRole.ADMIN, hashed_password=hash_password("bench"))
    db.add(admin); db.commit()
    token = create_access_token(str(admin.id), admin.role.value)

    # 2. bemenet
    log(f"Szintetikus bemenet generálása: {args.total_bytes:,} bájt, {args.file_count} fájl")
    g0 = time.monotonic()
    files = generate_sources(storage_root, project.id, args.total_bytes, args.file_count,
                             args.big_file_bytes, settings.media_object_prefix)
    g_elapsed = time.monotonic() - g0
    for f in files:
        db.add(Media(title=f["title"], project_id=project.id, storage_key=f["key"], size_bytes=f["size"],
                     checksum_sha256=f["sha256"], status="ready"))
    db.commit()
    report["generation"] = {
        "files": len(files),
        "bytes_written": sum(f["size"] for f in files),
        "bytes_allocated": sum(f["allocated_bytes"] for f in files),
        "seconds": round(g_elapsed, 3),
        "throughput_bytes_per_s": int(args.total_bytes / max(g_elapsed, 1e-6)),
        "generator_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    assert report["generation"]["bytes_allocated"] >= args.total_bytes * 0.99, "sparse fájl gyanú"
    log(f"Bemenet kész: {args.total_bytes:,} bájt {g_elapsed:.1f} s alatt")

    # 3. export: API-n létrehozás, külön worker-processz
    api_log = work_dir / "api.log"
    api_proc = Proc([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                     "--port", str(args.api_port), "--log-level", "warning"], env, api_log)
    try:
        wait_http("127.0.0.1", args.api_port, "/health")
        status, _, data = api("127.0.0.1", args.api_port, "POST",
                              f"/api/v1/projects/{project.id}/gallery-export", token)
        assert status == 201, (status, data[:300])
        job = json.loads(data)
        public_id = job["public_id"]
        log(f"Job létrehozva: {public_id} (várt csomagméret {job['expected_archive_bytes']:,} bájt)")

        e0 = time.monotonic()
        worker = subprocess.run(
            [sys.executable, "-m", "app.worker", "--once", "--log-level", "INFO"],
            env=env, cwd=str(BACKEND_DIR), capture_output=True, text=True, check=False,
        )
        e_elapsed = time.monotonic() - e0
        (work_dir / "worker.log").write_text(worker.stdout + worker.stderr)
        worker_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
        status, _, data = api("127.0.0.1", args.api_port, "GET", f"/api/v1/gallery-exports/{public_id}", token)
        job = json.loads(data)
        report["export"] = {
            "status": job["status"],
            "files": job["files_done"],
            "archive_bytes": job["object_size"],
            "expected_archive_bytes": job["expected_archive_bytes"],
            "size_matches_prediction": job["object_size"] == job["expected_archive_bytes"],
            "seconds": round(e_elapsed, 3),
            "throughput_bytes_per_s": int(args.total_bytes / max(e_elapsed, 1e-6)),
            "worker_peak_rss_bytes": worker_peak,
            "worker_returncode": worker.returncode,
            "archive_sha256": job["archive_sha256"],
            "error": job.get("error_message"),
        }
        assert job["status"] == "ready", job
        log(f"Export kész: {job['object_size']:,} bájt, {e_elapsed:.1f} s, worker csúcs-RSS {human(worker_peak)}")

        # 4. letöltés
        cut = job["object_size"] * 3 // 10
        got = download_with_interruption("127.0.0.1", args.api_port, public_id, token, job["object_size"], cut, report)
        report["download_hash_matches"] = got == job["archive_sha256"]
        assert report["download_hash_matches"], (got, job["archive_sha256"])
        api_proc.sample()
        report["api_peak_rss_bytes"] = api_proc.peak_rss
        log(f"Letöltés kész: {report['download']['bytes_received']:,} bájt, sha256 egyezik")
    finally:
        api_proc.stop()

    # 5. ZIP64 + integritás a tárolt objektumon (bájtra azonos a letöltöttel: sha256 egyezett)
    db.expire_all()
    from app.models.gallery_export import GalleryExportJob
    row = db.query(GalleryExportJob).filter_by(public_id=public_id).one()
    archive_path = storage_root / row.object_key
    log("ZIP64 ellenőrzés és minden bejegyzés hash-ellenőrzése...")
    verify_archive(archive_path, files, report)
    log(f"Ellenőrzés kész: {report['verification']['entries_hash_verified']} bejegyzés egyezik")

    report["total_seconds"] = round(time.monotonic() - t0, 3)
    report["verdict"] = "SIKERES"
    _write_report(report)
    db.close()
    if not args.keep:
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
