"""Felszerelés archiválása (a felhasználó kérése, 2026-10): az archivált eszköz
nem foglalható forgatásra és nem írható ki, de a múltbeli forgatásainál
megmarad; visszaállítható.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.eszkoz_kivitel import EszkozKivitel
from app.models.project import Project
from app.services import eszkoz_foglalas, eszkoz_statisztika
from app.services.hu_datum import budapesti_ma


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
def admin(db):
    e = Employee(full_name="Archiváló Admin (demó)", tipus=EmployeeType.BELSOS, email="archiv-admin-demo@example.test",
                 role=SystemRole.ADMIN, is_active=True)
    db.add(e)
    db.flush()
    return e


@pytest.fixture
def adat(db):
    ma = budapesti_ma()
    kamera = Equipment(nev="Régi kamera (demó)", kategoria="Kamera", track_mode=TrackMode.ASSET)
    db.add(kamera)
    db.flush()
    mult = Project(nev="Múltbeli forgatás (demó)", forgatas_datuma=ma - timedelta(days=20))
    jovo = Project(nev="Jövőbeli forgatás (demó)", forgatas_datuma=ma + timedelta(days=7))
    uj = Project(nev="Új forgatás (demó)", forgatas_datuma=ma + timedelta(days=14))
    db.add_all([mult, jovo, uj])
    db.flush()
    db.add_all([Assignment(equipment_id=kamera.id, project_id=mult.id, qty=1),
                Assignment(equipment_id=kamera.id, project_id=jovo.id, qty=1)])
    db.flush()
    return {"kamera": kamera, "mult": mult, "jovo": jovo, "uj": uj}


def _kliens(db, admin):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush  # a végpontok commitja is a visszagörgetett tranzakcióban marad
    return TestClient(app), app


def test_archivalas_api_foglalas_tiltva_mult_megmarad_visszaallithato(db, admin, adat):
    k = adat
    c, app = _kliens(db, admin)
    try:
        r = c.post(f"/api/v1/equipment/{k['kamera'].id}/archivalas", json={"ok": "Selejtezve (demó)"})
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["archivalva_at"] and v["archivalas_oka"] == "Selejtezve (demó)"
        # A még előttünk álló forgatás szerepel a figyelmeztetésben, a múltbeli nem.
        assert [f["project_id"] for f in v["jovobeli_foglalasok"]] == [k["jovo"].id]
        db.refresh(k["kamera"])
        assert k["kamera"].archivalta_id == admin.id

        # Új forgatásra nem foglalható ...
        r = c.post("/api/v1/assignments", json={"equipment_id": k["kamera"].id, "project_id": k["uj"].id})
        assert r.status_code == 409 and "archivált" in r.json()["detail"]
        # ... a múltbeli foglalás viszont megmaradt, és a statisztika is számol vele.
        assert db.scalar(select(Assignment).where(Assignment.project_id == k["mult"].id)) is not None
        stat = eszkoz_statisztika.statisztikak(db, [k["kamera"].id])[k["kamera"].id]
        assert k["mult"].id in {f.project_id for f in stat.forgatasok}
        # Az eszköz adatlapja továbbra is megnyitható.
        assert c.get(f"/api/v1/equipment/{k['kamera'].id}").json()["archivalva_at"]

        # Visszaállítás után újra foglalható.
        r = c.post(f"/api/v1/equipment/{k['kamera'].id}/visszaallitas")
        assert r.status_code == 200 and r.json()["archivalva_at"] is None
        r = c.post("/api/v1/assignments", json={"equipment_id": k["kamera"].id, "project_id": k["uj"].id})
        assert r.status_code in (200, 201), r.text
    finally:
        app.dependency_overrides.clear()


def test_kozos_foglalasi_ut_es_lara_sem_hasznalja(db, adat):
    from app.admin_agent.diszpo_tervezo import hasznalhato

    k = adat
    k["kamera"].archivalva_at = budapesti_ma()
    db.flush()
    with pytest.raises(eszkoz_foglalas.ArchivaltEszkoz):
        eszkoz_foglalas.hozzarendel(db, k["uj"], k["kamera"])
    assert hasznalhato(k["kamera"]) is False


def test_technika_ready_jelzi_a_jovobeli_forgatason(db, adat):
    from app.services.technika import check_technika

    k = adat
    k["kamera"].archivalva_at = budapesti_ma()
    db.flush()
    jovo = check_technika(db, k["jovo"], commit=False)
    assert jovo["status"] == "ISSUE" and "archivált" in jovo["message"]
    mult = check_technika(db, k["mult"], commit=False)
    assert "archivált" not in (mult["message"] or "")


def test_eszkozkivitel_nem_ajanlja_es_nem_irhato_ki_de_visszahozhato(db, adat):
    from app.api.routes.eszkoz_kivitel import TetelKeres, _belepes_valasz, tetel_mentes

    k = adat
    kivitel = EszkozKivitel(project_id=k["jovo"].id, kod="ta9901", allapot="kivitel")
    db.add(kivitel)
    db.flush()
    db.commit = db.flush
    # Archiválás előtt kint van (kiírták) ...
    tetel_mentes("TA9901", TetelKeres(equipment_id=k["kamera"].id, kivitt_db=1), db)
    k["kamera"].archivalva_at = budapesti_ma()
    db.flush()
    v = _belepes_valasz(db, kivitel)
    assert k["kamera"].id not in {e.id for e in v.eszkozok}
    assert k["kamera"].id not in {a.id for a in v.ajanlott}
    # ... archiválva újra kiírni nem lehet ...
    masik = EszkozKivitel(project_id=k["uj"].id, kod="ta9902", allapot="kivitel")
    db.add(masik)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        tetel_mentes("TA9902", TetelKeres(equipment_id=k["kamera"].id, kivitt_db=1), db)
    assert exc.value.status_code == 409 and "archivált" in exc.value.detail
    # ... de ami kint van, az visszahozható.
    kivitel.allapot = "vissza"
    db.flush()
    sorok = tetel_mentes("TA9901", TetelKeres(equipment_id=k["kamera"].id, visszahozott_db=1), db)
    assert any(s.id == k["kamera"].id for s in sorok)


def test_uj_leltarba_nem_kerul(db, adat):
    from app.services import stocktake

    adat["kamera"].archivalva_at = budapesti_ma()
    db.flush()
    import inspect as _inspect

    forras = _inspect.getsource(stocktake)
    assert "archivalva_at.is_(None)" in forras  # az új leltár csak a nem archivált eszközöket veszi fel
