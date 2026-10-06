"""Autóhoz felvitt, MÉG KI NEM FIZETETT számla (a felhasználó kérése,
2026-10): pl. szerviz, amiről számla jött, de még nem utaltuk el - csak a
fizetési határidő adható meg, és utólag a "Fizetés" gombbal (fizetés-
dátummal) jelölhető kifizetettnek. A tankolás-féle költés továbbra is
alapból azonnal kifizetett.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.auto import Auto
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense


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
def kliens(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Autó Admin (demó)", tipus=EmployeeType.BELSOS, email="auto-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    auto = Auto(rendszam="DEMO-001", megnevezes="Teszt furgon (demó)")
    db.add_all([admin, auto])
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield TestClient(app), auto
    finally:
        app.dependency_overrides.clear()


def test_tankolas_alapbol_azonnal_kifizetett(db, kliens):
    c, auto = kliens
    r = c.post(f"/api/v1/autok/{auto.id}/kiadasok",
               json={"megnevezes": "Tankolás (demó)", "osszeg": 20000, "fizetesi_mod": "Bankkártya", "datum": "2026-10-01"})
    assert r.status_code == 201, r.text
    e = db.get(Expense, r.json()["id"])
    assert e.kesz and e.fizetes_datuma == date(2026, 10, 1) and e.fizetes_hatarideje is None


def test_szerviz_kifizetetlenul_hataridovel_majd_fizetes(db, kliens):
    c, auto = kliens
    r = c.post(f"/api/v1/autok/{auto.id}/kiadasok",
               json={"megnevezes": "Szerviz (demó)", "osszeg": 150000, "plusz_afa": True, "fizetesi_mod": "Átutalás",
                     "kifizetve": False, "fizetes_hatarideje": "2026-10-20", "datum": "2026-10-05"})
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["kesz"] is False and v["fizetes_hatarideje"] == "2026-10-20" and v["datum"] is None
    e = db.get(Expense, v["id"])
    assert not e.kesz and e.fizetes_datuma is None

    # Az Utalásra váró listában is ott van, a határidővel.
    lista = c.get("/api/v1/finance/utalasra-varo").json()
    sor = next(t for t in lista if t["kulcs"] == f"auto_kiadas:{e.id}")
    assert sor["hatarido"] == "2026-10-20" and sor["kinek"] == "DEMO-001" and sor["tipus"] == "Autó"

    # Az autó lapján a kifizetetlen áll elöl.
    a = c.get(f"/api/v1/autok/{auto.id}").json()
    assert a["kiadasok"][0]["id"] == e.id

    # Fizetés gomb: kifizetve, a megadott dátummal.
    r = c.patch(f"/api/v1/autok/kiadasok/{e.id}", json={"kesz": True, "fizetes_datuma": "2026-10-18"})
    assert r.status_code == 200, r.text
    db.refresh(e)
    assert e.kesz and e.fizetes_datuma == date(2026, 10, 18)
    assert all(t["kulcs"] != f"auto_kiadas:{e.id}" for t in c.get("/api/v1/finance/utalasra-varo").json())

    # Visszavonás: újra fizetésre vár, fizetés-dátum nélkül.
    r = c.patch(f"/api/v1/autok/kiadasok/{e.id}", json={"kesz": False})
    assert r.status_code == 200, r.text
    db.refresh(e)
    assert not e.kesz and e.fizetes_datuma is None and e.fizetes_hatarideje == date(2026, 10, 20)


def test_kifizetetlenhez_hatarido_kell_a_keszpenzes_mindig_kifizetett(db, kliens):
    c, auto = kliens
    alap = {"megnevezes": "Szerviz (demó)", "osszeg": 1000, "kifizetve": False}
    r = c.post(f"/api/v1/autok/{auto.id}/kiadasok", json=alap | {"fizetesi_mod": "Átutalás"})
    assert r.status_code == 400 and "határidő" in r.json()["detail"]
    # Készpénz: a pénz helyben kiment - kifizetett, határidő nélkül (a régi szabály).
    r = c.post(f"/api/v1/autok/{auto.id}/kiadasok",
               json=alap | {"fizetesi_mod": "Készpénz", "fizetes_hatarideje": "2026-10-20", "datum": "2026-10-05"})
    assert r.status_code == 201, r.text
    e = db.get(Expense, r.json()["id"])
    assert e.kesz and e.fizetes_datuma == date(2026, 10, 5) and e.fizetes_hatarideje is None


def test_fizetes_gomb_csak_autos_kiadasra(db, kliens):
    c, _auto = kliens
    mas = Expense(megnevezes="Nem autós (demó)", netto=1000, tipus="egyeb")
    db.add(mas)
    db.flush()
    r = c.patch(f"/api/v1/autok/kiadasok/{mas.id}", json={"kesz": True})
    assert r.status_code == 404
