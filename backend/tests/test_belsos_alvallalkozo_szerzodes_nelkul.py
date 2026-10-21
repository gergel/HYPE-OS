"""Belsős munkatárs alvállalkozói kiadásban (a felhasználó kérése, 2026-10):
ha egy belsőst pluszban egy kiadáshoz hozzáadnak egy projekthez, az
Utókövetésben TIG kell tőle, de eseti SZERZŐDÉS NEM - a belsős ebben olyan,
mint egy keretszerződéses. Belsős = a FORGATÁS NAPJÁN belsős.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.api.routes import subcontractor_contracts as sc
from app.core.database import engine
from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.project import Project
from app.services.szamlazo import SzamlazoFel

NAP = date(2026, 5, 10)


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
def adat(db):
    admin = Employee(full_name="Belsős-teszt Admin (demó)", tipus=EmployeeType.BELSOS, email="bt-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    belsos = Employee(full_name="Plusz Belsős (demó)", tipus=EmployeeType.BELSOS, is_active=True)
    kesobbi = Employee(full_name="Később belsős (demó)", tipus=EmployeeType.BELSOS, is_active=True)
    kulsos = Employee(full_name="Plusz Külsős (demó)", tipus=EmployeeType.KULSOS, is_active=True)
    p = Project(nev="Plusz kiadásos forgatás (demó)", forgatas_datuma=NAP)
    db.add_all([admin, belsos, kesobbi, kulsos, p])
    db.flush()
    db.add_all([
        BelsosIdoszak(employee_id=belsos.id, kezdet=date(2026, 1, 1)),
        # A forgatás idején még külsős volt - tőle szerződés is kell.
        BelsosIdoszak(employee_id=kesobbi.id, kezdet=date(2026, 9, 1)),
    ])
    for e in (belsos, kesobbi, kulsos):
        db.add(Expense(megnevezes=f"Plusz munka {e.full_name}", netto=10_000, tipus="kulsos", employee_id=e.id,
                       alvallalkozo_project_id=p.id))
    db.flush()
    db.expire_all()
    return {"admin": admin, "belsos": belsos, "kesobbi": kesobbi, "kulsos": kulsos, "p": db.get(Project, p.id)}


def test_belsos_tig_kell_de_szerzodes_nem(db, adat):
    p = adat["p"]
    igenylok = {e.id for e in sc.szerzodest_igenylo_emberek(p)}
    # Papírozandó marad (TIG kell tőle) ...
    assert {adat["belsos"].id, adat["kesobbi"].id, adat["kulsos"].id} <= igenylok
    # ... de eseti szerződés nem: mint a keretszerződésesnél.
    assert sc._mentesul_keretszerzodessel([], NAP, SzamlazoFel(employee=adat["belsos"]))
    assert not sc._mentesul_keretszerzodessel([], NAP, SzamlazoFel(employee=adat["kesobbi"]))
    assert not sc._mentesul_keretszerzodessel([], NAP, SzamlazoFel(employee=adat["kulsos"]))
    assert not sc._mentesul_keretszerzodessel([], NAP)


def test_utokovetes_szerzodes_teendo_csak_a_nem_belsosoknek(db, adat):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: adat["admin"]
    db.commit = db.flush
    try:
        c = TestClient(app)
        r = c.get(f"/api/v1/alvallalkozoi-szerzodesek/{adat['p'].id}")
        assert r.status_code == 200, r.text
        teendo = {x["szamlazo"] for x in r.json()["pending"]}
        assert f"e{adat['belsos'].id}" not in teendo
        assert {f"e{adat['kesobbi'].id}", f"e{adat['kulsos'].id}"} <= teendo
        # A TIG viszont kell tőle - és rögtön készíthető (nincs mire várni).
        r = c.get(f"/api/v1/teljesitesi-igazolasok/{adat['p'].id}")
        assert r.status_code == 200, r.text
        assert f"e{adat['belsos'].id}" in {x["szamlazo"] for x in r.json()["pending"]}
        # Eseti szerződés a belsősnek nem is indítható - beszédes hibával.
        r = c.post(f"/api/v1/alvallalkozoi-szerzodesek/{adat['p'].id}/e{adat['belsos'].id}/save",
                   json={"netto_osszeg": 1000})
        assert r.status_code == 400 and "Belsős" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_hianyossag_matrixban_belsos_nem_hianyzo(db, adat):
    from app.services import utokovetes_hianyok as uh

    allapot, _ = uh._szerzodes_allapot(adat["p"], f"e{adat['belsos'].id}", {}, {}, SzamlazoFel(employee=adat["belsos"]))
    assert allapot == "belsos" and allapot not in uh.HIANYZO["szerzodes"]
    allapot, _ = uh._szerzodes_allapot(adat["p"], f"e{adat['kulsos'].id}", {}, {}, SzamlazoFel(employee=adat["kulsos"]))
    assert allapot == "hianyzik"
