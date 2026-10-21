"""Portál feltöltő link (a felhasználó kérése, 2026-10): mindenki csak a SAJÁT
feltöltéseit látja, és azokból törölni tud; a feltöltések párhuzamosan
mehetnek (egymástól független kérések, a feltöltő azonosítójával).

A tárhelyet (R2) és a videó-feldolgozást hamis függvények helyettesítik.
Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.portal import Portal, PortalFeltoltoLink, PortalFolder, PortalImage, PortalVideo

A = {"X-Feltolto-Kulcs": "a" * 32}
B = {"X-Feltolto-Kulcs": "b" * 32}


@pytest.fixture
def db():
    with engine.connect() as conn:
        tx = conn.begin()
        sess = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield sess
        finally:
            sess.close()
            tx.rollback()


@pytest.fixture
def k(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.routes import portal_admin
    from app.core.database import get_db
    from app.main import app
    from app.services import portal_storage

    tarhely = {"fel": [], "torolt": []}
    monkeypatch.setattr(portal_storage, "upload_file", lambda path, key, ct: tarhely["fel"].append(key) or key)
    monkeypatch.setattr(portal_storage, "upload_bytes", lambda data, key, ct: tarhely["fel"].append(key) or key)
    monkeypatch.setattr(portal_storage, "public_url", lambda key: f"https://r2.example/{key}")
    monkeypatch.setattr(portal_storage, "delete_prefix", lambda prefix: tarhely["torolt"].append(prefix))
    monkeypatch.setattr(portal_admin, "_enqueue_processing", lambda vid, key: None)

    p = Portal(slug="feltolto-teszt-" + uuid.uuid4().hex[:8], share_token=uuid.uuid4().hex, status="live",
               title_override="Feltöltő teszt (demó)", brand="hype")
    db.add(p)
    db.flush()
    admin_mappa = PortalFolder(portal_id=p.id, name="Nyersanyag", sort_order=0)
    link = PortalFeltoltoLink(portal_id=p.id, token=uuid.uuid4().hex)
    db.add_all([admin_mappa, link])
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "db": db, "p": p, "mappa": admin_mappa, "t": link.token, "tarhely": tarhely}
    finally:
        app.dependency_overrides.clear()


U = "/api/v1/public/portal/feltoltes"


def _video(k, fej, folder_id=None, nev="klip.mp4"):
    data = {"folder_id": str(folder_id)} if folder_id else {}
    r = k["c"].post(f"{U}/{k['t']}/video", headers=fej, data=data, files={"file": (nev, io.BytesIO(b"v" * 100), "video/mp4")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _kep(k, fej, folder_id=None, nev="kep.png"):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (20, 10), "red").save(buf, format="PNG")
    data = {"folder_id": str(folder_id)} if folder_id else {}
    r = k["c"].post(f"{U}/{k['t']}/kep", headers=fej, data=data, files={"file": (nev, buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_mindenki_csak_a_sajatjat_latja(k):
    c, t, mappa = k["c"], k["t"], k["mappa"]
    # A két mappát hoz létre, B egyet; mindketten feltöltenek az admin mappába is.
    a1 = c.post(f"{U}/{t}/mappa", headers=A, json={"name": "A első"}).json()["id"]
    a2 = c.post(f"{U}/{t}/mappa", headers=A, json={"name": "A második"}).json()["id"]
    b1 = c.post(f"{U}/{t}/mappa", headers=B, json={"name": "B mappa"}).json()["id"]
    va = _video(k, A, a1)
    _kep(k, A, a2)
    _video(k, A, mappa.id, "a-nyers.mp4")
    _video(k, B, b1)
    _video(k, B, mappa.id, "b-nyers.mp4")

    la = c.get(f"{U}/{t}", headers=A).json()
    assert {f["name"] for f in la["folders"]} == {"Nyersanyag", "A első", "A második"}  # B mappája nem látszik
    assert {f["title"] for f in la["fajlok"]} == {"klip", "kep", "a-nyers"}
    nyers = next(f for f in la["folders"] if f["name"] == "Nyersanyag")
    assert nyers["video_db"] == 1 and nyers["sajat"] is False  # csak a saját darabszám
    assert next(f for f in la["folders"] if f["name"] == "A első")["sajat"] is True
    assert any(f["id"] == va and f["tipus"] == "video" for f in la["fajlok"])

    lb = c.get(f"{U}/{t}", headers=B).json()
    assert {f["name"] for f in lb["folders"]} == {"Nyersanyag", "B mappa"}
    assert {f["title"] for f in lb["fajlok"]} == {"klip", "b-nyers"}

    # Azonosító nélkül: csak az admin mappák, fájl semmi.
    l0 = c.get(f"{U}/{t}").json()
    assert {f["name"] for f in l0["folders"]} == {"Nyersanyag"} and l0["fajlok"] == []
    # B nem tölthet fel A mappájába, és azonosító nélkül nem lehet feltölteni.
    r = c.post(f"{U}/{t}/video", headers=B, data={"folder_id": str(a1)},
               files={"file": ("x.mp4", io.BytesIO(b"x"), "video/mp4")})
    assert r.status_code == 404
    assert c.post(f"{U}/{t}/mappa", json={"name": "névtelen"}).status_code == 400


def test_csak_a_sajat_torolheto(k):
    c, t, db, mappa = k["c"], k["t"], k["db"], k["mappa"]
    va = _video(k, A, mappa.id)
    kb = _kep(k, B, mappa.id)
    assert c.delete(f"{U}/{t}/video/{va}", headers=B).status_code == 404  # másé nem
    assert c.delete(f"{U}/{t}/kep/{kb}", headers=A).status_code == 404
    assert c.delete(f"{U}/{t}/video/{va}", headers=A).status_code == 204
    assert db.get(PortalVideo, va) is None and f"videos/{va}" in k["tarhely"]["torolt"]
    assert c.delete(f"{U}/{t}/kep/{kb}", headers=B).status_code == 204
    assert db.get(PortalImage, kb) is None
    # Az admin mappáját a feltöltő nem törölheti.
    assert c.delete(f"{U}/{t}/mappa/{mappa.id}", headers=A).status_code == 404


def test_sajat_mappa_torlese_a_sajat_fajlokkal(k):
    c, t, db = k["c"], k["t"], k["db"]
    m = c.post(f"{U}/{t}/mappa", headers=A, json={"name": "A mappa"}).json()["id"]
    v = _video(k, A, m)
    i = _kep(k, A, m)
    # Ha más is tett bele valamit (pl. az admin), nem törölhető.
    idegen = PortalImage(portal_id=k["p"].id, folder_id=m, title="admin kép")
    db.add(idegen)
    db.flush()
    assert c.delete(f"{U}/{t}/mappa/{m}", headers=A).status_code == 400
    db.delete(idegen)
    db.flush()
    assert c.delete(f"{U}/{t}/mappa/{m}", headers=B).status_code == 404
    assert c.delete(f"{U}/{t}/mappa/{m}", headers=A).status_code == 204
    assert db.get(PortalFolder, m) is None and db.get(PortalVideo, v) is None and db.get(PortalImage, i) is None
    assert {f"videos/{v}", f"images/{i}"} <= set(k["tarhely"]["torolt"])


def test_mappara_szukitett_link(k):
    c, db, mappa = k["c"], k["db"], k["mappa"]
    masik = PortalFolder(portal_id=k["p"].id, name="Másik", sort_order=1)
    link = PortalFeltoltoLink(portal_id=k["p"].id, folder_id=mappa.id, token=uuid.uuid4().hex)
    db.add_all([masik, link])
    db.flush()
    k2 = {**k, "t": link.token}
    v = _video(k2, A, masik.id)  # a kért mappa mindegy: a link mappájába megy
    assert db.get(PortalVideo, v).folder_id == mappa.id
    adat = c.get(f"{U}/{link.token}", headers=A).json()
    assert adat["csak_mappa"] is True and [f["name"] for f in adat["folders"]] == ["Nyersanyag"]
    assert [f["id"] for f in adat["fajlok"]] == [v]
