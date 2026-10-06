"""E-Rezsi (a felhasználó kérése, 2026-10): előfizetésnél a lejárat dátuma
NEM kötelező - biztosításnál/autópapírnál továbbra is az.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole


@pytest.fixture
def c(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Rezsi Admin (demó)", tipus=EmployeeType.BELSOS, email="rezsi-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    db.add(admin)
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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


def _uj(c, **kw):
    alap = {"nev": "Adobe (demó)", "tipus": "elofizetes", "ciklus": "eves", "ar_osszeg": 120000, "ar_penznem": "HUF"}
    return c.post("/api/v1/kotelezettsegek", json=alap | kw)


def test_elofizetes_lejarat_nelkul_mentheto(c):
    for ciklus in ("havi", "eves", "egyszeri"):
        r = _uj(c, ciklus=ciklus, nev=f"Előfizetés {ciklus} (demó)")
        assert r.status_code == 201, r.text
        assert r.json()["kovetkezo_fordulo"] is None
    # Megadva is elfogadja (csak tájékoztató).
    r = _uj(c, kovetkezo_fordulo="2027-01-31")
    assert r.status_code == 201 and r.json()["kovetkezo_fordulo"] == "2027-01-31"


def test_biztositasnal_tovabbra_is_kotelezo(c):
    r = _uj(c, tipus="biztositas", nev="Kötelező biztosítás (demó)")
    assert r.status_code == 400 and "lejárat" in r.json()["detail"]
