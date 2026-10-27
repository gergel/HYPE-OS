"""Utómunka felvezetése (a felhasználó kérése): a felvezetésnél "Esemény neve"
és "Forgatás dátuma" kell (nem "Anyag neve" és "Határidő"), az anyag neve
pedig ezekből és a projektkódból áll össze: <esemény>_<ÉÉÉÉ.HH.NN>_<kód a
HYPE előtag nélkül> - pl. HYPE26-0001 helyett 26-0001.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.deliverable import Deliverable
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.project import Project
from app.services.project_actions import create_utomunka, utomunka_nev

D = "/api/v1/deliverables"


def test_nevkepzes_szabalya():
    assert utomunka_nev("Horizon szöveg", date(2026, 10, 13), "HYPE26-0388") == "Horizon szöveg_2026.10.13_26-0388"
    assert utomunka_nev("  Esemény ", None, "HYPE26-0001") == "Esemény_26-0001"
    assert utomunka_nev("Rövid kód", date(2026, 1, 2), "AB1") == "Rövid kód_2026.01.02_AB1"


@pytest.fixture
def k():
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    with engine.connect() as conn:
        tx = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        admin = Employee(full_name="Utómunka Név Admin (demó)", tipus=EmployeeType.BELSOS, role=SystemRole.ADMIN,
                         email="utomunka-nev-demo@example.test", is_active=True)
        db.add(admin)
        db.flush()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: admin
        db.commit = db.flush
        try:
            yield {"c": TestClient(app), "db": db, "admin": admin}
        finally:
            app.dependency_overrides.clear()
            db.close()
            tx.rollback()


def test_felvezetes_esemenybol_datumbol_es_kodbol_rakja_ossze_a_nevet(k):
    c, db = k["c"], k["db"]
    r = c.post(D, json={"esemeny_neve": "TTM Horizon demó", "projektkod_szoveg": "HYPE26-9931",
                        "forgatas_datuma": "2026-10-13"})
    assert r.status_code == 201, r.text
    d = db.get(Deliverable, r.json()["id"])
    assert d.projekt_neve == "TTM Horizon demó_2026.10.13_26-9931"
    assert d.esemeny_neve == "TTM Horizon demó" and d.forgatas_datuma_notion == "2026.10.13"
    assert d.projektkod_szoveg == "HYPE26-9931" and d.hatarido is None

    # Ugyanazzal a három adattal második anyag nem jön létre (duplikátum-védelem).
    assert c.post(D, json={"esemeny_neve": "TTM Horizon demó", "projektkod_szoveg": "HYPE26-9931",
                           "forgatas_datuma": "2026-10-13"}).status_code != 201
    # A forgatás dátuma nem kötelező: nélküle a név <esemény>_<kód>.
    r = c.post(D, json={"esemeny_neve": "TTM Horizon demó", "projektkod_szoveg": "HYPE26-9931"})
    assert r.status_code == 201, r.text
    d = db.get(Deliverable, r.json()["id"])
    assert d.projekt_neve == "TTM Horizon demó_26-9931" and d.forgatas_datuma_notion is None
    # Esemény neve nélkül (és kész név nélkül) nincs miből nevet képezni.
    r = c.post(D, json={"projektkod_szoveg": "HYPE26-9931", "forgatas_datuma": "2026-10-14"})
    assert r.status_code == 400 and "esemény nevét" in r.json()["detail"]
    # Aki kész nevet küld (pl. az AI Assistant), annál az marad.
    r = c.post(D, json={"projekt_neve": "Kész név (demó)", "projektkod_szoveg": "HYPE26-9931"})
    assert r.status_code == 201 and r.json()["projekt_neve"] == "Kész név (demó)"


def test_projekt_oldali_gomb_ugyanazt_a_formatumot_adja(k):
    db = k["db"]
    p = Project(nev="Projekt gomb demó", forgatas_datuma=date(2026, 10, 15), projektkod_szoveg="HYPE26-9932")
    db.add(p)
    db.flush()
    assert create_utomunka(db, p, k["admin"]).projekt_neve == "Projekt gomb demó_2026.10.15_26-9932"
