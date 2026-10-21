"""Kiadás: „Egyéni ÁFA összeg" — a számlán szereplő ÁFA konkrét összege,
nem százalék (lásd routes/finance._afa_brutto).

Tiszta egységtesztek a bruttó-számításra (DB nélkül), plusz egy API-teszt
felvitelre és módosításra (a saját sorát törli)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes.finance import _afa_brutto


def test_egyeni_afa_osszeg_brutto_pontosan_netto_plusz_afa():
    adat = {"netto": 100000, "plusz_afa": "egyeni", "egyeni_afa_osszege": 18350}
    _afa_brutto(adat)
    assert adat["brutto"] == 118350
    assert adat["plusz_afa"] == "igen"  # minden más kimutatás ÁFÁ-snak látja
    assert adat["afa_szazalek"] == 18.35  # tájékoztató, az összegből


def test_egyeni_afa_osszeg_nelkul_hiba():
    with pytest.raises(HTTPException) as e:
        _afa_brutto({"netto": 1000, "plusz_afa": "egyeni"})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        _afa_brutto({"netto": 1000, "plusz_afa": "egyeni", "egyeni_afa_osszege": -5})


def test_szazalekra_vagy_afa_nelkulire_valtas_torli_az_egyeni_osszeget():
    szazalek = {"afa_szazalek": 27}
    _afa_brutto(szazalek, netto=1000, plusz_afa="igen", egyeni_afa=300)
    assert szazalek["egyeni_afa_osszege"] is None and szazalek["brutto"] == 1270

    nincs = {"plusz_afa": ""}
    _afa_brutto(nincs, netto=1000, plusz_afa="igen", egyeni_afa=300)
    assert nincs["egyeni_afa_osszege"] is None and nincs["brutto"] == 1000


def test_netto_javitas_megtartja_az_egyeni_afat():
    """Egy meglévő, egyéni ÁFÁ-s soron a nettó átírása: az ÁFA összege marad."""
    adat = {"netto": 2000}
    _afa_brutto(adat, plusz_afa="igen", afa_szazalek=15, egyeni_afa=300)
    assert adat["brutto"] == 2300 and "egyeni_afa_osszege" not in adat


def test_kezzel_irt_brutto_nyer():
    adat = {"netto": 1000, "plusz_afa": "egyeni", "egyeni_afa_osszege": 100, "brutto": 1111}
    _afa_brutto(adat)
    assert adat["brutto"] == 1111


def test_api_felvitel_es_modositas():
    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError
    from fastapi.testclient import TestClient

    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.main import app
    from app.models.finance import Expense

    db = SessionLocal()
    try:
        db.execute(select(1))
    except OperationalError:
        pytest.skip("Postgres nem elérhető — integrációs teszt kihagyva.")
    c = TestClient(app)
    h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
    r = c.post("/api/v1/expenses", headers=h, json={
        "megnevezes": "Egyéni ÁFA teszt Kft.", "netto": 50000, "plusz_afa": "egyeni",
        "egyeni_afa_osszege": 9000, "fizetes_datuma": "2026-09-20", "kifizetes_modja": "Átutalás",
    })
    assert r.status_code in (200, 201), r.text
    eid = r.json()["id"]
    try:
        d = r.json()
        assert float(d["brutto"]) == 59000 and float(d["egyeni_afa_osszege"]) == 9000 and d["plusz_afa"] == "igen"
        # Devizás felvezetés: az egyéni ÁFA is forintra vált.
        r = c.patch(f"/api/v1/expenses/{eid}", headers=h, json={
            "netto": 100, "plusz_afa": "egyeni", "egyeni_afa_osszege": 27, "penznem": "EUR", "arfolyam": 400,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert float(d["brutto"]) == 50800 and float(d["egyeni_afa_osszege"]) == 10800
        # Százalékra váltás: az egyéni összeg törlődik.
        r = c.patch(f"/api/v1/expenses/{eid}", headers=h, json={"plusz_afa": "igen", "afa_szazalek": 27})
        d = r.json()
        assert d["egyeni_afa_osszege"] is None and float(d["brutto"]) == 50800
    finally:
        db.query(Expense).filter(Expense.id == eid).delete(synchronize_session=False)
        db.commit()
        db.close()
