"""Projektkódhoz felvezetett kiadás (a felhasználó kérése, 2026-10): ha
megadják a kiadás dátumát, az már KIFIZETETT - "Külsős" besorolásnál is, és
akkor is, ha a dátum utólag kerül rá. Kivétel az alvállalkozós kiadás (annak a
kifizetése a TIG-jén megy), és a kifejezetten "nincs kifizetve" jelölés.

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
def k(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Kifizetett Admin (demó)", tipus=EmployeeType.BELSOS, email="kif-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    alv = Employee(full_name="Kifizetett Alvállalkozó (demó)", tipus=EmployeeType.KULSOS, is_active=True)
    pc = ProjectCode(projektkod="KIF26-0001 (demó)")
    db.add_all([admin, alv, pc])
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    szamlalo = iter(range(1, 100))

    def uj(**kw):
        n = next(szamlalo)
        adat = {"megnevezes": f"Cég {n} (demó)", "kiadas_leiras": "Vonatjegy (demó)", "netto": 1000 * n,
                "project_code_id": pc.id, "kifizetes_modja": "Átutalás", "plusz_afa": "", "tipus": "egyeb"}
        r = c.post("/api/v1/expenses", json=adat | kw)
        assert r.status_code == 201, r.text
        return r.json()

    c = TestClient(app)
    try:
        yield {"c": c, "uj": uj, "alv": alv, "pc": pc}
    finally:
        app.dependency_overrides.clear()


def test_datummal_felvezetett_kiadas_kifizetett(k):
    assert k["uj"](fizetes_datuma="2026-10-01")["kesz"] is True
    # "Külsős" besorolásnál is (eddig nyitott maradt).
    assert k["uj"](tipus="kulsos", fizetes_datuma="2026-10-01")["kesz"] is True
    # Dátum nélkül nyitott marad.
    assert k["uj"]()["kesz"] is False
    # Kifejezett "nincs kifizetve" nyer.
    assert k["uj"](tipus="kulsos", fizetes_datuma="2026-10-01", kesz=False)["kesz"] is False


def test_alvallalkozos_kiadas_a_tig_en_fizetodik(k):
    d = k["uj"](tipus="kulsos", employee_id=k["alv"].id, fizetes_datuma="2026-10-01")
    assert d["kesz"] is False


def test_utolag_megadott_datum_is_kifizetette_teszi(k):
    c = k["c"]
    d = k["uj"]()
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"fizetes_datuma": "2026-10-02"})
    assert r.status_code == 200 and r.json()["kesz"] is True
    # Utólag projektkódra tett, dátumos külsős kiadás is.
    d = k["uj"](project_code_id=None, tipus="kulsos")
    r = c.patch(f"/api/v1/expenses/{d['id']}", json={"fizetes_datuma": "2026-10-03", "project_code_id": k["pc"].id})
    assert r.json()["kesz"] is True
    # Alvállalkozósnál és készpénzesnél utólag sem (TIG, ill. házipénztár).
    d = k["uj"](tipus="kulsos", employee_id=k["alv"].id)
    assert c.patch(f"/api/v1/expenses/{d['id']}", json={"fizetes_datuma": "2026-10-04"}).json()["kesz"] is False
    d = k["uj"](kifizetes_modja="Készpénz")
    assert c.patch(f"/api/v1/expenses/{d['id']}", json={"fizetes_datuma": "2026-10-05"}).json()["kesz"] is False
