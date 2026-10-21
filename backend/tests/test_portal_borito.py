"""Portál borítókép: új feltöltés új URL-t kap (nincs gyorsítótár-beragadás),
a törlés csak a régi fájlt viszi, és a jelszavas oldal márkát is kap az alap
háttérhez. A tárhelyet (R2) hamis függvények helyettesítik."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError


@pytest.fixture()
def kornyezet(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.routes import portal_admin
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.main import app
    from app.models.portal import Portal

    try:
        db = SessionLocal()
        db.execute(select(1))
    except OperationalError:
        pytest.skip("Postgres nem elérhető.")
    feltoltott: list[str] = []
    torolt: list[str] = []
    monkeypatch.setattr(portal_admin.storage, "upload_file",
                        lambda path, key, ct: (feltoltott.append(key), f"https://r2.example/{key}")[1])
    monkeypatch.setattr(portal_admin.storage, "delete_prefix", lambda prefix: torolt.append(prefix))
    p = Portal(slug="borito-teszt-" + uuid.uuid4().hex[:8], share_token=uuid.uuid4().hex, status="live",
               title_override="Borító teszt", brand="hype")
    db.add(p)
    db.commit()
    c = TestClient(app)
    h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
    try:
        yield c, h, p.id, p.slug, feltoltott, torolt
    finally:
        db.rollback()
        obj = db.get(Portal, p.id)
        if obj is not None:
            db.delete(obj)
            db.commit()
        db.close()


def _feltolt(c, h, pid):
    r = c.post(f"/api/v1/portal-admin/{pid}/cover", headers=h, files={"file": ("borito.JPG", b"kep", "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["cover_image_url"]


def test_uj_borito_uj_url_es_a_regi_torlodik(kornyezet):
    c, h, pid, _, feltoltott, torolt = kornyezet
    elso = _feltolt(c, h, pid)
    masodik = _feltolt(c, h, pid)
    assert elso != masodik  # új URL → a böngésző/CDN nem a régit adja
    assert feltoltott[0].startswith(f"covers/{pid}/cover-") and feltoltott[0].endswith(".jpg")
    assert torolt == [feltoltott[0]]  # csak a régi fájl, nem az egész mappa


def test_torles_utan_ures_borito_es_csak_a_regi_fajl_megy(kornyezet):
    c, h, pid, slug, feltoltott, torolt = kornyezet
    _feltolt(c, h, pid)
    r = c.delete(f"/api/v1/portal-admin/{pid}/cover", headers=h)
    assert r.status_code == 200 and r.json()["cover_image_url"] == ""
    assert torolt == [feltoltott[0]]
    publikus = c.get(f"/api/v1/public/portal/{slug}").json()
    assert publikus["project"]["cover_image_url"] == ""  # → a portál az alap hátteret mutatja


def test_jelszavas_portal_markat_is_kuld(kornyezet):
    from app.core.database import SessionLocal
    from app.models.portal import Portal
    from app.core.security import hash_password

    c, _, pid, slug, _, _ = kornyezet
    db = SessionLocal()
    db.get(Portal, pid).password_hash = hash_password("titok")
    db.commit()
    db.close()
    d = c.get(f"/api/v1/public/portal/{slug}").json()
    assert d["locked"] is True and d["brand"] == "hype" and d["cover_image_url"] == ""
