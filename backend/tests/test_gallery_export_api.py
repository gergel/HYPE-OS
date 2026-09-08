"""Galéria-export: végponttól végpontig, jogosultság, idempotencia, letöltés/Range."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.gallery_export import ExportStatus, GalleryExportJob
from app.models.timeline import TimelineEvent
from app.services.gallery_export import make_download_token, utcnow
from app.worker import run_once
from tests.conftest import Seed, auth


def _create(client: TestClient, seed: Seed, user, project_id: int):
    return client.post(f"/api/v1/projects/{project_id}/gallery-export", headers=auth(user))


def _download_all(client: TestClient, url: str) -> tuple[int, dict, bytes]:
    with client.stream("GET", url) as response:
        body = b"".join(response.iter_bytes())
        return response.status_code, dict(response.headers), body


def _ready_job(client: TestClient, seed: Seed, db, storage, project=None, user=None) -> dict:
    project = project or seed.project_a
    user = user or seed.admin
    seed.small_gallery(project)
    response = _create(client, seed, user, project.id)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"
    counts = run_once(db, storage)
    assert counts == {"ready": 1, "failed": 0, "retry": 0}
    job = client.get(f"/api/v1/gallery-exports/{response.json()['public_id']}", headers=auth(user)).json()
    assert job["status"] == "ready"
    return job


# --- E2E: kis csomag -----------------------------------------------------------


def test_small_gallery_end_to_end_extract_and_hash(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    assert job["progress_percent"] == 100.0
    assert job["files_done"] == job["file_count"] == 5
    assert job["object_size"] == job["expected_archive_bytes"]
    assert job["expires_at"] is not None

    ticket = client.post(f"/api/v1/gallery-exports/{job['public_id']}/download-url", headers=auth(seed.admin))
    assert ticket.status_code == 200, ticket.text
    ticket = ticket.json()
    assert ticket["size"] == job["object_size"]
    assert ticket["direct"] is False  # lokális backend: saját Range-képes végpont

    status, headers, body = _download_all(client, ticket["url"])
    assert status == 200
    assert headers["content-type"] == "application/zip"
    assert headers["accept-ranges"] == "bytes"
    assert int(headers["content-length"]) == len(body) == job["object_size"]
    assert headers["etag"] == f'"{job["archive_sha256"]}"'
    assert "attachment;" in headers["content-disposition"]
    assert "filename*=UTF-8''" in headers["content-disposition"]
    assert "ALFA-001-Alfa-forg" in headers["content-disposition"]
    assert hashlib.sha256(body).hexdigest() == job["archive_sha256"]

    # kibontás + minden fájl tartalmi hash-e egyezik a forrással
    expected = {hashlib.sha256(content).hexdigest() for content in seed.files[seed.project_a.id].values()}
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        assert len(names) == 5
        assert any(name.startswith("Válogatás/") for name in names)
        got = {hashlib.sha256(zf.read(name)).hexdigest() for name in names}
    assert got == expected

    events = db.scalars(select(TimelineEvent).where(TimelineEvent.event_type == "GalleryExportReady")).all()
    assert len(events) == 1


def test_dangerous_and_duplicate_names_inside_archive(client, seed, db, storage):
    folder = seed.add_folder(seed.project_a, "../../etc")
    seed.add_media(seed.project_a, "../../../passwd", b"1", folder=folder, ext="jpg")
    seed.add_media(seed.project_a, "kép", b"22", ext="jpg")
    seed.add_media(seed.project_a, "KÉP", b"333", ext="JPG")
    seed.add_media(seed.project_a, "CON", b"4444", ext="png")
    seed.add_media(seed.project_a, "日本語 ファイル", b"55555", ext="heic")
    response = _create(client, seed, seed.admin, seed.project_a.id)
    assert response.status_code == 201
    assert run_once(db, storage)["ready"] == 1
    job = db.scalars(select(GalleryExportJob)).one()
    body = b"".join(storage.read_stream(job.object_key))
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        names = sorted(zf.namelist())
    assert ".._.._etc/.._.._.._passwd.jpg" in names, "path traversal semlegesítve, mappa is"
    assert "_CON.png" in names, "Windows-foglalt név"
    assert "日本語 ファイル.heic" in names, "Unicode név megmarad (UTF-8 flag)"
    kep_variants = sorted(n for n in names if n.casefold().startswith("kép"))
    assert len(kep_variants) == 2 and any(" (2)." in n for n in kep_variants), kep_variants
    assert len({n.casefold() for n in names}) == len(names), "kis/nagybetű-független egyediség"
    assert not any(n.startswith("/") or n.split("/")[0] == ".." for n in names)


# --- Idempotencia / dupla kattintás -----------------------------------------------


def test_double_click_is_idempotent(client, seed, db, storage):
    seed.small_gallery(seed.project_a)
    first = _create(client, seed, seed.admin, seed.project_a.id)
    second = _create(client, seed, seed.admin, seed.project_a.id)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["public_id"] == second.json()["public_id"]
    assert db.scalar(select(GalleryExportJob.id).where(GalleryExportJob.project_id == seed.project_a.id)) is not None
    assert len(db.scalars(select(GalleryExportJob)).all()) == 1

    run_once(db, storage)
    third = _create(client, seed, seed.admin, seed.project_a.id)
    assert third.status_code == 200
    assert third.json()["status"] == "ready"
    assert third.json()["public_id"] == first.json()["public_id"], "kész export újrahasznosítva"


def test_page_reopen_finds_same_job_without_client_state(client, seed, db, storage):
    seed.small_gallery(seed.project_a)
    created = _create(client, seed, seed.admin, seed.project_a.id).json()
    state = client.get(f"/api/v1/projects/{seed.project_a.id}/gallery-export", headers=auth(seed.admin)).json()
    assert state["plan"]["file_count"] == 5
    assert state["job"]["public_id"] == created["public_id"]
    assert state["job"]["status"] == "queued"
    run_once(db, storage)
    state = client.get(f"/api/v1/projects/{seed.project_a.id}/gallery-export", headers=auth(seed.admin)).json()
    assert state["job"]["status"] == "ready"
    assert state["job"]["public_id"] == created["public_id"]


def test_empty_gallery_is_409(client, seed):
    response = _create(client, seed, seed.admin, seed.project_a.id)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "empty_gallery"
    state = client.get(f"/api/v1/projects/{seed.project_a.id}/gallery-export", headers=auth(seed.admin)).json()
    assert state["job"] is None and "ready" in state["unavailable_reason"]


# --- Forrásváltozás -> új export ----------------------------------------------------


def test_source_change_requires_new_export(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    seed.add_media(seed.project_a, "új kép", b"uj tartalom")
    state = client.get(f"/api/v1/projects/{seed.project_a.id}/gallery-export", headers=auth(seed.admin)).json()
    assert state["job"] is None, "a régi kész export nem tartozik az új galéria-verzióhoz"
    assert state["plan"]["file_count"] == 6
    response = _create(client, seed, seed.admin, seed.project_a.id)
    assert response.status_code == 201
    assert response.json()["public_id"] != job["public_id"]
    assert response.json()["source_fingerprint"] != job["source_fingerprint"]
    # a régi kész csomag megmarad a TTL-ig
    old = client.get(f"/api/v1/gallery-exports/{job['public_id']}", headers=auth(seed.admin)).json()
    assert old["status"] == "ready"


# --- Jogosultság / bérlő-elkülönítés -------------------------------------------------


def test_unauthenticated_is_401(client, seed):
    seed.small_gallery(seed.project_a)
    assert client.post(f"/api/v1/projects/{seed.project_a.id}/gallery-export").status_code == 401
    assert client.get(f"/api/v1/projects/{seed.project_a.id}/gallery-export").status_code == 401
    assert client.get("/api/v1/gallery-exports").status_code == 401
    assert client.get("/api/v1/gallery-exports/x").status_code == 401
    assert client.post("/api/v1/gallery-exports/x/download-url").status_code == 401
    assert client.get("/api/v1/gallery-exports/x/download?token=nope").status_code == 403


def test_other_tenant_cannot_see_create_or_download(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)  # Alfa Kft galériája, admin indította
    pid = job["public_id"]
    b = seed.ugyfel_b  # Béta Zrt ügyfele

    # létrehozás/lekérdezés idegen projekten: 404 (a létezés sem derül ki)
    assert _create(client, seed, b, seed.project_a.id).status_code == 404
    assert client.get(f"/api/v1/projects/{seed.project_a.id}/gallery-export", headers=auth(b)).status_code == 404
    assert client.get(f"/api/v1/gallery-exports/{pid}", headers=auth(b)).status_code == 404
    assert client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(b)).status_code == 404
    assert client.get("/api/v1/gallery-exports", headers=auth(b)).json() == []

    # a másik bérlő által kiadott, érvényes jeggyel sem tölthető le
    forged = make_download_token(db.scalars(select(GalleryExportJob)).one(), b.id, utcnow() + timedelta(minutes=5))
    assert client.get(f"/api/v1/gallery-exports/{pid}/download?token={forged}").status_code == 404

    # a saját bérlő ügyfele viszont igen
    a = seed.ugyfel_a
    assert client.get(f"/api/v1/gallery-exports/{pid}", headers=auth(a)).status_code == 200
    assert [j["public_id"] for j in client.get("/api/v1/gallery-exports", headers=auth(a)).json()] == [pid]
    ticket = client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(a))
    assert ticket.status_code == 200
    status, _, body = _download_all(client, ticket.json()["url"])
    assert status == 200 and hashlib.sha256(body).hexdigest() == job["archive_sha256"]


def test_ugyfel_without_tenant_sees_nothing(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    orphan = seed.ugyfel_orphan
    assert _create(client, seed, orphan, seed.project_a.id).status_code == 404
    assert client.get(f"/api/v1/gallery-exports/{job['public_id']}", headers=auth(orphan)).status_code == 404
    assert client.get("/api/v1/gallery-exports", headers=auth(orphan)).json() == []


def test_token_for_other_job_or_tampered_is_rejected(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    pid = job["public_id"]
    good = client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(seed.admin)).json()["url"]
    token = good.split("token=")[1]
    tampered = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    assert client.get(f"/api/v1/gallery-exports/{pid}/download?token={tampered}").status_code == 403
    assert client.get(f"/api/v1/gallery-exports/masik-id/download?token={token}").status_code == 403


def test_revoked_user_cannot_use_issued_link(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    url = client.post(f"/api/v1/gallery-exports/{job['public_id']}/download-url", headers=auth(seed.ugyfel_a)).json()["url"]
    seed.ugyfel_a.is_active = False
    db.commit()
    assert client.get(url).status_code == 403


def test_media_and_portal_crud_reads_now_require_auth(client, seed):
    seed.small_gallery(seed.project_a)
    for path in ("/api/v1/media", "/api/v1/folders", "/api/v1/portal", "/api/v1/payments"):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=auth(seed.ugyfel_a)).status_code == 403, path
        assert client.get(path, headers=auth(seed.admin)).status_code == 200, path


# --- Letöltés: Range, lejárt link megújítása, végső hash ----------------------------------


def test_range_resume_across_link_renewal_final_hash(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    pid = job["public_id"]
    size = job["object_size"]

    first_url = client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(seed.admin)).json()["url"]
    head = client.head(first_url)
    assert head.status_code == 200 and int(head.headers["content-length"]) == size
    etag = head.headers["etag"]

    # 1) megszakított letöltés: csak az első 40%-ot olvassuk el
    cut = size * 4 // 10
    with client.stream("GET", first_url) as response:
        assert response.status_code == 200
        partial = b""
        for chunk in response.iter_bytes(chunk_size=4096):
            partial += chunk
            if len(partial) >= cut:
                break
    partial = partial[:cut]

    # 2) a régi link lejárt -> 410, majd megújítás ugyanarra az objektumra
    expired = make_download_token(db.scalars(select(GalleryExportJob)).one(), seed.admin.id, utcnow() - timedelta(seconds=1))
    assert client.get(f"/api/v1/gallery-exports/{pid}/download?token={expired}").status_code == 410
    renewed = client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(seed.admin)).json()
    assert renewed["etag"] == job["object_etag"] and renewed["size"] == size
    assert "/download?token=" in renewed["url"]

    # 3) folytatás Range + If-Range-dzsel az új linken
    with client.stream("GET", renewed["url"], headers={"Range": f"bytes={cut}-", "If-Range": etag}) as response:
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes {cut}-{size - 1}/{size}"
        assert int(response.headers["content-length"]) == size - cut
        assert response.headers["etag"] == etag
        rest = b"".join(response.iter_bytes())
    assert len(partial) + len(rest) == size
    assert hashlib.sha256(partial + rest).hexdigest() == job["archive_sha256"]
    with zipfile.ZipFile(io.BytesIO(partial + rest)) as zf:
        assert zf.testzip() is None


def test_range_edge_cases(client, seed, db, storage):
    job = _ready_job(client, seed, db, storage)
    size = job["object_size"]
    url = client.post(f"/api/v1/gallery-exports/{job['public_id']}/download-url", headers=auth(seed.admin)).json()["url"]
    full = _download_all(client, url)[2]

    r = client.get(url, headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and r.content == full[:100] and r.headers["content-range"] == f"bytes 0-99/{size}"
    r = client.get(url, headers={"Range": "bytes=-100"})
    assert r.status_code == 206 and r.content == full[-100:]
    r = client.get(url, headers={"Range": f"bytes={size}-"})
    assert r.status_code == 416 and r.headers["content-range"] == f"bytes */{size}"
    r = client.get(url, headers={"Range": "bytes=0-99", "If-Range": '"masik-etag"'})
    assert r.status_code == 200 and len(r.content) == size, "eltérő If-Range -> teljes tartalom"
    r = client.get(url, headers={"Range": "bytes=0-9,20-29"})
    assert r.status_code == 200 and len(r.content) == size, "több tartomány -> teljes tartalom"


def test_download_url_not_ready_or_expired(client, seed, db, storage):
    seed.small_gallery(seed.project_a)
    pid = _create(client, seed, seed.admin, seed.project_a.id).json()["public_id"]
    r = client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(seed.admin))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_ready"
    run_once(db, storage)
    job = db.scalars(select(GalleryExportJob)).one()
    job.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    r = client.post(f"/api/v1/gallery-exports/{pid}/download-url", headers=auth(seed.admin))
    assert r.status_code == 410 and r.json()["detail"]["code"] == "expired"
    assert client.get(f"/api/v1/gallery-exports/{pid}", headers=auth(seed.admin)).json()["status"] == "expired"
    # lejárt után ugyanarra a verzióra újra kérhető: ugyanaz a sor újraindul
    again = _create(client, seed, seed.admin, seed.project_a.id)
    assert again.status_code == 201 and again.json()["status"] == "queued" and again.json()["public_id"] == pid


def test_gallery_finalized_hook_prepares_export(seed, db, storage):
    from app.services.gallery_export import prepare_export_on_gallery_finalized

    seed.small_gallery(seed.project_a)
    job = prepare_export_on_gallery_finalized(db, seed.project_a.id, storage=storage)
    assert job is not None and job.status is ExportStatus.QUEUED
    assert prepare_export_on_gallery_finalized(db, seed.project_a.id, storage=storage).id == job.id
    assert prepare_export_on_gallery_finalized(db, seed.project_b.id, storage=storage) is None  # üres galéria
