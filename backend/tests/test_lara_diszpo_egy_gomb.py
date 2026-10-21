"""Lara egygombos brief / technika (a felhasználó kérése, 2026-10): a
tanultak alapján megírja a kész brief-szöveget, ill. összeállítja a
technikai csomagot - de CSAK OLVAS: semmit nem ír a projektre, nem foglal
eszközt (azt a gombot nyomó ember teszi meg a saját jogával). Leállított
Laránál nem fut.

VALÓDI MODELLHÍVÁS NINCS (hamis adapter). Tranzakcióban fut a helyi
adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent import llm
from app.core.database import engine
from app.models.admin_agent import AdminAgentSetting
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project


@pytest.fixture
def db():
    with engine.connect() as conn:
        tx = conn.begin()
        sess = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield sess
        finally:
            llm.teszt_adapter(None)
            sess.close()
            tx.rollback()


@pytest.fixture
def k(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Egygomb Admin (demó)", tipus=EmployeeType.BELSOS, email="egygomb-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    p = Project(nev="Konferencia felvétel (demó)", forgatas_datuma=date.today() + timedelta(days=30),
                helyszin="Budapest (demó)", description="Kétkamerás konferencia-felvétel, interjúkkal (demó).")
    kamera = Equipment(nev="Egygomb kamera (demó)", kategoria="Kamera", track_mode=TrackMode.ASSET)
    db.add_all([admin, p, kamera])
    db.flush()
    llm.teszt_adapter(lambda r, f, s: {
        "brief": "Sziasztok! Konferenciát rögzítünk két kamerával (demó).",
        "technika": [{"equipment_id": kamera.id, "qty": 1, "indoklas": "fő kamera (demó)"}],
        "indoklas": "teszt", "feladat_ertelmezes": "Konferencia rögzítése (demó)", "figyelmeztetesek": [],
    })
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "p": p, "kamera": kamera}
    finally:
        app.dependency_overrides.clear()


def _general(k, resz):
    return k["c"].post(f"/api/v1/admin-agent/diszpo/{k['p'].id}/generalas", json={"resz": resz})


def test_brief_kesz_szoveg_es_nem_ir_a_projektre(db, k):
    r = _general(k, "brief")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["brief"].startswith("Sziasztok! Konferenciát rögzítünk") and v["technika"] == []
    assert v["feladat_ertelmezes"] == "Konferencia rögzítése (demó)"
    db.refresh(k["p"])
    assert not k["p"].brief


def test_technika_lista_es_nem_foglal(db, k):
    r = _general(k, "technika")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["brief"] is None
    assert [t["equipment_id"] for t in v["technika"]] == [k["kamera"].id]
    assert db.scalar(select(Assignment).where(Assignment.project_id == k["p"].id)) is None


def test_ervenytelen_resz_400(k):
    assert _general(k, "mas").status_code == 400


def test_leallitott_laranal_nem_fut(db, k):
    s = db.get(AdminAgentSetting, 1)
    if s is None:
        s = AdminAgentSetting(id=1)
        db.add(s)
    s.kill_switch = True
    db.flush()
    assert _general(k, "brief").status_code == 423
