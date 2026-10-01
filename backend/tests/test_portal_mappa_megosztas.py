"""Portál mappa-megosztás: a kimásolt mappa linkjén az almappák is látszanak
(a felhasználó kérése, 2026-10). Elszigetelt SQLite, éles adatot nem érint."""

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.portal_public import megosztas
from app.models import Base
from app.models.portal import Portal, PortalFolder, PortalImage, PortalVideo


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture
def db():
    engine = sa.create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sess = sessionmaker(engine, expire_on_commit=False)()
    try:
        yield sess
    finally:
        sess.close()


def _fa(db):
    """Fő > Kimásolt > (Al > Mély), (Rejtett > RejtettAlatt) + egy testvér mappa."""
    p = Portal(slug="mappa-teszt", status="live", title_override="Teszt")
    db.add(p)
    db.flush()
    m = {}
    for nev, szulo, rejtett, token in [
        ("Fő", None, False, None),
        ("Kimásolt", "Fő", False, "mappa-token"),
        ("Al", "Kimásolt", False, None),
        ("Mély", "Al", False, None),
        ("Rejtett", "Kimásolt", True, None),
        ("RejtettAlatt", "Rejtett", False, None),
        ("Testvér", "Fő", False, None),
    ]:
        f = PortalFolder(portal_id=p.id, name=nev, parent_folder_id=m[szulo].id if szulo else None,
                         rejtett=rejtett, share_token=token)
        db.add(f)
        db.flush()
        m[nev] = f
    for nev in m:
        db.add(PortalVideo(portal_id=p.id, title=f"v-{nev}", status="ready", folder_id=m[nev].id))
        db.add(PortalImage(portal_id=p.id, key=f"images/{nev}.jpg", title=f"k-{nev}", folder_id=m[nev].id))
    db.add(PortalVideo(portal_id=p.id, title="v-Al-feldolgozas", status="processing", folder_id=m["Al"].id))
    db.add(PortalVideo(portal_id=p.id, title="v-Al-rejtett", status="ready", rejtett=True, folder_id=m["Al"].id))
    db.commit()
    return m


def test_megosztott_mappa_almappai_es_tartalmuk_is_latszanak(db):
    m = _fa(db)
    d = megosztas("mappa-token", db)
    assert d["tipus"] == "mappa"
    pr = d["project"]
    mappak = {f["name"]: f for f in pr["folders"]}
    assert set(mappak) == {"Kimásolt", "Al", "Mély"}
    # A megosztott mappa a link nézetében főszintű (a nézet innen építi a fát).
    assert mappak["Kimásolt"]["parent_folder_id"] is None
    assert mappak["Al"]["parent_folder_id"] == m["Kimásolt"].id
    assert mappak["Mély"]["parent_folder_id"] == m["Al"].id
    assert {v["title"] for v in pr["videos"]} == {"v-Kimásolt", "v-Al", "v-Mély"}
    assert {i["title"] for i in pr["images"]} == {"k-Kimásolt", "k-Al", "k-Mély"}


def test_rejtett_megosztott_mappa_sajat_linkje_el(db):
    m = _fa(db)
    m["Kimásolt"].rejtett = True
    db.commit()
    pr = megosztas("mappa-token", db)["project"]
    assert {f["name"] for f in pr["folders"]} == {"Kimásolt", "Al", "Mély"}


def test_letoltes_engedi_az_almappa_fajljait(db):
    from app.api.routes.portal_exports import Access, allowed

    m = _fa(db)
    _, kepek, videok = allowed(db, Access(part="mappa-token"))
    al_kep = next(i for i in m["Al"].images)
    testver_kep = next(i for i in m["Testvér"].images)
    assert al_kep.id in kepek and testver_kep.id not in kepek
    assert {v.id for v in m["Mély"].videos} <= videok
