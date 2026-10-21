"""Kiadásról a PROJEKTKÓD vagy az ALVÁLLALKOZÓ levétele (a felhasználó kérése,
2026-10): a PATCH null-lal kiszedi, és a régi forgatás-hozzárendelés
(alvallalkozo_project_id) sem marad bent - különben a levett ember ott
maradna az Utókövetésben szerződés/TIG-teendőként.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.project import Project
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
def adat(db):
    admin = Employee(full_name="Levétel Admin (demó)", tipus=EmployeeType.BELSOS, email="levetel-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Levétel Külsős (demó)", tipus=EmployeeType.KULSOS, is_active=True)
    pk1 = ProjectCode(projektkod="LEVETEL-DEMO-1")
    pk2 = ProjectCode(projektkod="LEVETEL-DEMO-2")
    db.add_all([admin, kulsos, pk1, pk2])
    db.flush()
    f1 = Project(nev="Levétel forgatás 1 (demó)", forgatas_datuma=date(2026, 9, 1), project_code_id=pk1.id)
    f2 = Project(nev="Levétel forgatás 2 (demó)", forgatas_datuma=date(2026, 9, 2), project_code_id=pk2.id)
    db.add_all([f1, f2])
    db.flush()
    k = Expense(megnevezes="Levétel Kft. (demó)", netto=10_000, fizetes_datuma=date(2026, 9, 3), tipus="kulsos",
                employee_id=kulsos.id, project_code_id=pk1.id, alvallalkozo_project_id=f1.id)
    db.add(k)
    db.flush()
    return {"admin": admin, "kulsos": kulsos, "pk1": pk1, "pk2": pk2, "f1": f1, "f2": f2, "kiadas": k}


def _kliens(db, admin):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    return TestClient(app), app


def _patch(db, adat, body):
    c, app = _kliens(db, adat["admin"])
    try:
        r = c.patch(f"/api/v1/expenses/{adat['kiadas'].id}", json=body)
        assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.clear()
    db.refresh(adat["kiadas"])
    return adat["kiadas"]


def test_alvallalkozo_levetele_a_forgatast_is_leveszi(db, adat):
    k = _patch(db, adat, {"employee_id": None})
    assert k.employee_id is None and k.alvallalkozo_project_id is None
    assert k.project_code_id == adat["pk1"].id
    assert adat["kulsos"] not in adat["f1"].alvallalkozo_stab


def test_projektkod_levetele_a_forgatast_is_leveszi(db, adat):
    k = _patch(db, adat, {"project_code_id": None})
    assert k.project_code_id is None and k.alvallalkozo_project_id is None
    assert k.employee_id == adat["kulsos"].id


def test_projektkod_csereje_az_uj_forgatasra_kot(db, adat):
    k = _patch(db, adat, {"project_code_id": adat["pk2"].id})
    assert k.project_code_id == adat["pk2"].id
    assert k.alvallalkozo_project_id == adat["f2"].id


def test_mas_mezo_szerkesztese_nem_nyul_a_hozzarendeleshez(db, adat):
    k = _patch(db, adat, {"kiadas_leiras": "Javított leírás (demó)", "project_code_id": adat["pk1"].id})
    assert k.alvallalkozo_project_id == adat["f1"].id
