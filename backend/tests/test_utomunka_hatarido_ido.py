"""Utómunka határideje percre pontosan (a felhasználó kérése): a határidő
alapból csak nap, de bekapcsolhatóan óra:perc is megadható mellé
(hatarido_ido). A határidő törlése az időpontot is viszi.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.services.detail_tabs import get_field_tab_map
from app.services.entity_registry import get_field_types

D = "/api/v1/deliverables"


@pytest.fixture
def k():
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    with engine.connect() as conn:
        tx = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        admin = Employee(full_name="Határidő Idő Admin (demó)", tipus=EmployeeType.BELSOS, role=SystemRole.ADMIN,
                         email="hatarido-ido-demo@example.test", is_active=True)
        db.add(admin)
        db.flush()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: admin
        db.commit = db.flush
        try:
            yield {"c": TestClient(app), "db": db}
        finally:
            app.dependency_overrides.clear()
            db.close()
            tx.rollback()


def _uj_vagas(c) -> dict:
    r = c.post(D, json={"esemeny_neve": "Határidő demó", "projektkod_szoveg": "HYPE26-9941", "hatarido": "2026-10-30"})
    assert r.status_code == 201, r.text
    return r.json()


def test_alapbol_csak_datum_es_bekapcsolhato_a_pontos_idopont(k):
    c = k["c"]
    d = _uj_vagas(c)
    assert d["hatarido"] == "2026-10-30"
    assert d["hatarido_ido"] is None

    r = c.patch(f"{D}/{d['id']}", json={"hatarido_ido": "14:30"})
    assert r.status_code == 200, r.text
    assert r.json()["hatarido_ido"] == "14:30:00"
    assert r.json()["hatarido"] == "2026-10-30"

    lista = c.get(D).json()
    sor = next(x for x in (lista["items"] if isinstance(lista, dict) else lista) if x["id"] == d["id"])
    assert sor["hatarido_ido"] == "14:30:00"

    # Kikapcsolás: az időpont törlődik, a nap marad.
    r = c.patch(f"{D}/{d['id']}", json={"hatarido_ido": None})
    assert r.json()["hatarido_ido"] is None
    assert r.json()["hatarido"] == "2026-10-30"


def test_a_hatarido_torlese_az_idopontot_is_torli(k):
    c = k["c"]
    d = _uj_vagas(c)
    c.patch(f"{D}/{d['id']}", json={"hatarido_ido": "09:05"})
    r = c.patch(f"{D}/{d['id']}", json={"hatarido": None})
    assert r.status_code == 200, r.text
    assert r.json()["hatarido"] is None
    assert r.json()["hatarido_ido"] is None


def test_az_idopont_tipusa_ido_es_a_hatarido_fulehez_tartozik(k):
    db = k["db"]
    assert get_field_types("deliverable", db)["hatarido_ido"] == {"type": "time"}
    tabs = get_field_tab_map(db, "deliverable")
    if "hatarido" in tabs:
        assert tabs["hatarido_ido"] == tabs["hatarido"]
