#!/usr/bin/env python3
"""UI végponttól-végpontig teszt (Playwright + valódi backend + valódi Next.js build).

Lefedi: bejelentkezés a UI-n, csomag kérése, "Várakozó" állapot, oldal újratöltése
(bezárás/újranyitás) után ugyanaz a job, worker futtatása, "Kész" + 100%,
letöltés a böngészőből és a letöltött fájl sha256-ának egyezése, "Hibás" és
"Lejárt" és "Készülő" állapotok megjelenítése. Képernyőképeket és naplót ment.

Futtatás (a frontend előzetesen buildelve: ``cd frontend && npm run build``)::

    cd backend && .venv/bin/python scripts/ui_e2e_gallery_export.py
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
EVIDENCE_DIR = BACKEND_DIR.parent / "docs" / "gallery-export-evidence"
SHOTS_DIR = EVIDENCE_DIR / "ui"
API_PORT = 8000   # a Next.js build NEXT_PUBLIC_API_URL alapértéke: http://localhost:8000
WEB_PORT = 3000
CHROME = os.environ.get("CHROME_EXECUTABLE", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

sys.path.insert(0, str(BACKEND_DIR))

LOG_LINES: list[str] = []


def log(message: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {message}"
    print(line, flush=True)
    LOG_LINES.append(line)


def check(condition: bool, message: str) -> None:
    log(("OK   " if condition else "FAIL ") + message)
    if not condition:
        raise AssertionError(message)


def wait_http(port: int, path: str, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            conn.request("GET", path)
            if conn.getresponse().status < 500:
                return
        except OSError:
            time.sleep(0.4)
    raise RuntimeError(f"Nem indult el: {port}{path}")


def api(method: str, path: str, token: str, body: bytes | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", API_PORT, timeout=60)
    conn.request(method, path, body=body, headers={"Authorization": f"Bearer {token}"})
    response = conn.getresponse()
    data = response.read()
    return response.status, (json.loads(data) if data else {})


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="hype-ui-e2e-"))
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    for old in SHOTS_DIR.glob("*.png"):
        old.unlink()
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{work}/e2e.db",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_ROOT": str(work / "storage"),
        "SECRET_KEY": "ui-e2e-secret-not-for-production",
        "EXPORT_PROGRESS_INTERVAL_SECONDS": "0",
        "CORS_ORIGINS": f"http://localhost:{WEB_PORT},http://127.0.0.1:{WEB_PORT}",
        "ENVIRONMENT": "e2e",
        "PYTHONUNBUFFERED": "1",
    }
    for key in ("DATABASE_URL", "STORAGE_BACKEND", "LOCAL_STORAGE_ROOT", "SECRET_KEY",
                "EXPORT_PROGRESS_INTERVAL_SECONDS", "CORS_ORIGINS", "ENVIRONMENT"):
        os.environ[key] = env[key]

    from app.core.database import SessionLocal, engine
    from app.core.security import create_access_token, hash_password
    from app.models import Base
    from app.models.client import Client
    from app.models.employee import Employee, EmployeeType, SystemRole
    from app.models.gallery_export import ExportStatus, GalleryExportJob
    from app.models.media import Folder, Media
    from app.models.project import Project
    from app.models.project_code import ProjectCode
    from app.services.storage import LocalObjectStorage

    Base.metadata.create_all(engine)
    storage = LocalObjectStorage(work / "storage")
    db = SessionLocal()
    client = Client(nev="UI Teszt Kft"); db.add(client); db.flush()
    code = ProjectCode(projektkod="UI-001", client_id=client.id); db.add(code); db.flush()
    project = Project(nev="UI forgatás", project_code_id=code.id); db.add(project); db.flush()
    project2 = Project(nev="Hibás forgatás", project_code_id=code.id); db.add(project2); db.flush()
    admin = Employee(full_name="UI Admin", tipus=EmployeeType.BELSOS, email="admin@ui.test",
                     role=SystemRole.ADMIN, hashed_password=hash_password("titok123"))
    db.add(admin); db.flush()
    folder = Folder(nev="Válogatás", project_id=project.id); db.add(folder); db.flush()
    sources: dict[str, str] = {}
    for index in range(5):
        content = os.urandom(150_000 + index * 1000)
        key = f"media/{project.id}/kep-{index}.jpg"
        with storage.open_write(key) as out:
            out.write(content)
        db.add(Media(title=f"Forgatás kép {index}", project_id=project.id, storage_key=key,
                     folder_id=folder.id if index % 2 else None, size_bytes=len(content),
                     checksum_sha256=hashlib.sha256(content).hexdigest(), status="ready"))
        sources[key] = hashlib.sha256(content).hexdigest()
    # 2. projekt: a forrás hiányzik a tárból -> a worker "Hibás" állapotot ad
    db.add(Media(title="hiányzó", project_id=project2.id, storage_key=f"media/{project2.id}/nincs.jpg",
                 size_bytes=10, status="ready"))
    db.commit()
    token = create_access_token(str(admin.id), admin.role.value)

    api_log = (work / "api.log").open("ab")
    web_log = (work / "web.log").open("ab")
    api_proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                 "--port", str(API_PORT), "--log-level", "warning"],
                                env=env, cwd=str(BACKEND_DIR), stdout=api_log, stderr=subprocess.STDOUT)
    web_proc = subprocess.Popen(["npx", "next", "start", "-p", str(WEB_PORT)],
                                env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"},
                                cwd=str(FRONTEND_DIR), stdout=web_log, stderr=subprocess.STDOUT)
    try:
        wait_http(API_PORT, "/health")
        wait_http(WEB_PORT, "/login")
        log("Backend és frontend fut.")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True,
                                          locale="hu-HU")
            page = context.new_page()
            page.set_default_timeout(20_000)

            # --- 1. bejelentkezés a UI-n ---
            page.goto(f"http://localhost:{WEB_PORT}/login")
            page.fill("input[type=email]", "admin@ui.test")
            page.fill("input[type=password]", "titok123")
            page.click("button[type=submit]")
            page.wait_for_url(f"http://localhost:{WEB_PORT}/dashboard")
            check(page.evaluate("() => !!localStorage.getItem('hype_os_token')"), "bejelentkezés, token a böngészőben")

            # --- 2. galéria oldal, terv látszik ---
            gallery_url = f"http://localhost:{WEB_PORT}/projektek/{project.id}/galeria"
            page.goto(gallery_url)
            page.wait_for_selector("[data-testid=export-plan]")
            plan_text = page.inner_text("[data-testid=export-plan]")
            check("5 fájl" in plan_text, f"terv: {plan_text}")
            page.screenshot(path=str(SHOTS_DIR / "01-terv.png"))

            # --- 3. csomag kérése + dupla kattintás ---
            button = page.locator("[data-testid=export-create]")
            button.click()
            try:
                button.click(timeout=300)  # ha még látszik, második kattintás
            except Exception:  # noqa: BLE001 - a gomb már eltűnt: rendben
                pass
            page.wait_for_selector("[data-testid=export-status][data-status=queued]")
            check(page.inner_text("[data-testid=export-status]") == "Várakozó", "állapot: Várakozó")
            page.screenshot(path=str(SHOTS_DIR / "02-varakozo.png"))
            status, jobs = api("GET", "/api/v1/gallery-exports", token)
            check(status == 200 and len(jobs) == 1, f"dupla kattintás után is 1 job (db={len(jobs)})")
            public_id = jobs[0]["public_id"]

            # --- 4. oldal bezárása/újranyitása: új lap, ugyanaz a job ---
            page.close()
            page = context.new_page()
            page.set_default_timeout(20_000)
            page.goto(gallery_url)
            page.wait_for_selector("[data-testid=export-status][data-status=queued]")
            check(True, "újranyitás után ugyanaz a várakozó job látszik (szerveroldali állapot)")
            page.screenshot(path=str(SHOTS_DIR / "03-ujranyitas.png"))

            # --- 5. "Készülő" állapot valós előrehaladással (DB-ből szimulált 40%) ---
            row = db.query(GalleryExportJob).filter_by(public_id=public_id).one()
            row.status = ExportStatus.RUNNING
            row.bytes_done = row.total_source_bytes * 4 // 10
            row.files_done = 2
            row.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            db.commit()
            page.wait_for_selector("[data-testid=export-status][data-status=running]")
            percent = page.inner_text("[data-testid=export-percent]")
            check(percent == "40%", f"Készülő állapot, valós százalék a szerverről: {percent}")
            page.screenshot(path=str(SHOTS_DIR / "04-keszulo-40.png"))
            row.status = ExportStatus.QUEUED
            row.bytes_done = 0
            row.files_done = 0
            row.lease_expires_at = None
            db.commit()

            # --- 6. worker futtatása -> Kész ---
            worker = subprocess.run([sys.executable, "-m", "app.worker", "--once"], env=env,
                                    cwd=str(BACKEND_DIR), capture_output=True, text=True, check=False)
            check(worker.returncode == 0 and "'ready': 1" in worker.stdout, f"worker: {worker.stdout.strip()}")
            page.wait_for_selector("[data-testid=export-status][data-status=ready]")
            check(page.inner_text("[data-testid=export-percent]") == "100%", "Kész állapot, 100%")
            check("5/5 fájl" in page.inner_text("[data-testid=export-progress-text]"), "5/5 fájl")
            page.screenshot(path=str(SHOTS_DIR / "05-kesz.png"))

            # --- 7. letöltés a böngészőből ---
            with page.expect_download() as download_info:
                page.click("[data-testid=export-download]")
            download = download_info.value
            target = work / download.suggested_filename
            download.save_as(str(target))
            _status, job = api("GET", f"/api/v1/gallery-exports/{public_id}", token)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            check(digest == job["archive_sha256"], f"letöltött fájl sha256 egyezik ({download.suggested_filename})")
            check(target.stat().st_size == job["object_size"], f"méret {target.stat().st_size} == {job['object_size']}")
            with zipfile.ZipFile(target) as zf:
                check(zf.testzip() is None and len(zf.namelist()) == 5, "ZIP kibontható, 5 bejegyzés")
                got = {hashlib.sha256(zf.read(n)).hexdigest() for n in zf.namelist()}
            check(got == set(sources.values()), "minden bejegyzés hash-e egyezik a forrással")
            page.wait_for_selector("[data-testid=export-ticket]")
            page.screenshot(path=str(SHOTS_DIR / "06-letoltes.png"))

            # --- 8. Hibás állapot (hiányzó forrás) ---
            status, _ = api("POST", f"/api/v1/projects/{project2.id}/gallery-export", token)
            check(status == 201, "2. projekt exportja létrehozva")
            subprocess.run([sys.executable, "-m", "app.worker", "--once"], env=env, cwd=str(BACKEND_DIR),
                           capture_output=True, text=True, check=False)
            page.goto(f"http://localhost:{WEB_PORT}/projektek/{project2.id}/galeria")
            page.wait_for_selector("[data-testid=export-status][data-status=failed]")
            err = page.inner_text("[data-testid=export-error]")
            check("hiányzik" in err, f"Hibás állapot + emberi hibaüzenet: {err}")
            check(page.locator("[data-testid=export-create]").inner_text() == "Új csomag kérése", "újrakérés gomb")
            page.screenshot(path=str(SHOTS_DIR / "07-hibas.png"))

            # --- 9. Lejárt állapot ---
            db.expire_all()
            row = db.query(GalleryExportJob).filter_by(public_id=public_id).one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
            page.goto(gallery_url)
            page.wait_for_selector("[data-testid=export-status][data-status=expired]")
            check(page.inner_text("[data-testid=export-status]") == "Lejárt", "Lejárt állapot")
            page.screenshot(path=str(SHOTS_DIR / "08-lejart.png"))

            browser.close()
        log("UI E2E: minden ellenőrzés sikeres.")
        return 0
    finally:
        for proc in (web_proc, api_proc):
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        api_log.close(); web_log.close()
        db.close()
        (EVIDENCE_DIR / "ui-e2e.log").write_text(
            "# UI végponttól-végpontig teszt (Playwright/Chromium + uvicorn + next start)\n"
            "# parancs: cd backend && .venv/bin/python scripts/ui_e2e_gallery_export.py\n"
            f"generated={datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n" + "\n".join(LOG_LINES) + "\n"
        )
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"E2E FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
