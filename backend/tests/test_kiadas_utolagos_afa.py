"""Projektkódos kiadás (a felhasználó hibajelzése, 2026-10): ha a kiadást
"Nincs ÁFA"-val vezették fel, és UTÓLAG adják meg az ÁFA százalékát (az
adatlapon csak az "ÁFA %" mező mentődik), a bruttó automatikusan
újraszámolódik.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.project_code import ProjectCode


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
def c(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="ÁFA Admin (demó)", tipus=EmployeeType.BELSOS, email="afa-utolag-demo@example.test",
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


def _kiadas(c, db, **kw):
    pc = ProjectCode(projektkod="AFA26-9999 (demó)")
    db.add(pc)
    db.flush()
    alap = {
        "megnevezes": "Vonatjegy Kft. (demó)", "kiadas_leiras": "Vonatjegy (demó)", "netto": 10000,
        "plusz_afa": "", "kifizetes_modja": "Átutalás", "tipus": "egyeb", "project_code_id": pc.id,
    }
    r = c.post("/api/v1/expenses", json=alap | kw)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_utolag_megadott_afa_szazalek_kiszamolja_a_bruttot(c, db):
    d = _kiadas(c, db)
    assert float(d["brutto"]) == 10000  # "Nincs ÁFA": bruttó = nettó
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"afa_szazalek": 27})
    assert r.status_code == 200, r.text
    assert float(r.json()["brutto"]) == 12700 and r.json()["plusz_afa"] == "igen"
    # Más kulcsra javítva is követi.
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"afa_szazalek": 5})
    assert float(r.json()["brutto"]) == 10500
    # A nettó javítása a megadott százalékkal számol tovább.
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"netto": 20000})
    assert float(r.json()["brutto"]) == 21000


def test_nulla_szazalek_es_kifejezett_nincs_afa_nem_jelol(c, db):
    d = _kiadas(c, db)
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"afa_szazalek": 0})
    assert float(r.json()["brutto"]) == 10000 and r.json()["plusz_afa"] in ("", None)
    # Ha a kérés kifejezetten "Nincs ÁFA"-t mond, az nyer.
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"afa_szazalek": 27, "plusz_afa": ""})
    assert float(r.json()["brutto"]) == 10000
    # Kézzel beírt bruttó is nyer.
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"afa_szazalek": 27, "brutto": 11111})
    assert float(r.json()["brutto"]) == 11111
