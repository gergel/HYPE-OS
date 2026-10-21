"""Kiadás és projektkód kifizetett-állapota mindkét irányban (a felhasználó
kérése, 2026-10):

- a projektkódon felvezetett (dátum nélküli) tétel a "Fizetés" gombbal
  (kesz + fizetés dátuma) a Kiadások közé kerül;
- a Kiadások közé felvezetett tétel már kifizetett: projektkódhoz rendelve
  ott is eleve "Kifizetve" áll - a régi, dátumos, de nem jelölt soroknál is,
  kivéve a TIG-ből keletkezettet és a készpénzest.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate
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

    admin = Employee(full_name="Kifiz Admin (demó)", tipus=EmployeeType.BELSOS, email="kifiz-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Kifiz Külsős (demó)", tipus=EmployeeType.KULSOS, is_active=True)
    pk = ProjectCode(projektkod="KIFIZ-DEMO-1")
    db.add_all([admin, kulsos, pk])
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "pk": pk, "kulsos": kulsos}
    finally:
        app.dependency_overrides.clear()


def _projektkodon(db, k, expense_id):
    db.expire_all()
    j = k["c"].get(f"/api/v1/project-codes/{k['pk'].id}/bontas").json()
    return next(s for s in j["kiadasok"] if s["id"] == expense_id)


def test_projektkodon_felvezetett_fizetessel_a_kiadasok_koze_kerul(db, k):
    r = k["c"].post("/api/v1/expenses", json={"megnevezes": "MÁV (demó)", "kiadas_leiras": "Vonatjegy", "netto": 5000,
                                               "project_code_id": k["pk"].id, "tipus": "egyeb"})
    e = db.get(Expense, r.json()["id"])
    assert not e.kesz and e.fizetes_datuma is None and _projektkodon(db, k, e.id)["kifizetve"] is False
    k["c"].patch(f"/api/v1/expenses/{e.id}", json={"kesz": True, "fizetes_datuma": "2026-10-05"})
    db.refresh(e)
    # A Kiadások lista ezeket mutatja: kifizetett, dátummal (lásd KiadasokKartya).
    assert e.kesz and e.fizetes_datuma == date(2026, 10, 5)
    assert _projektkodon(db, k, e.id)["kifizetve"] is True


def test_kiadasokba_felvezetett_alvallalkozos_tetel_kifizetett_es_projektkodon_is(db, k):
    # A Kiadások űrlapja kesz=true-val küld (a fizetés dátuma ott kötelező).
    r = k["c"].post("/api/v1/expenses", json={"megnevezes": "Kifiz Bt. (demó)", "kiadas_leiras": "Munka", "netto": 40000,
                                               "fizetes_datuma": "2026-10-04", "kifizetes_modja": "Átutalás",
                                               "tipus": "kulsos", "employee_id": k["kulsos"].id, "kesz": True})
    assert r.status_code == 201, r.text
    e = db.get(Expense, r.json()["id"])
    k["c"].patch(f"/api/v1/expenses/{e.id}", json={"project_code_id": k["pk"].id})
    assert _projektkodon(db, k, e.id)["kifizetve"] is True


def test_regi_datumos_nem_jelolt_sor_hozzarendeleskor_kifizetett_lesz(db, k):
    e = Expense(megnevezes="Régi vonat (demó)", netto=3000, fizetes_datuma=date(2026, 3, 1), tipus="kulsos",
                kifizetes_modja="Átutalás", kesz=False)
    db.add(e)
    db.flush()
    k["c"].patch(f"/api/v1/expenses/{e.id}", json={"project_code_id": k["pk"].id})
    db.refresh(e)
    assert e.kesz is True


@pytest.mark.parametrize("eset", ["datum_nelkul", "keszpenz", "tig"])
def test_kivetelek_nem_valnak_kifizetette(db, k, eset):
    e = Expense(megnevezes=f"Kivétel {eset} (demó)", netto=1000, tipus="kulsos", kesz=False,
                fizetes_datuma=None if eset == "datum_nelkul" else date(2026, 3, 1),
                kifizetes_modja="Készpénz" if eset == "keszpenz" else "Átutalás")
    db.add(e)
    db.flush()
    if eset == "tig":
        db.add(PerformanceCertificate(employee_id=k["kulsos"].id, expense_id=e.id))
        db.flush()
    k["c"].patch(f"/api/v1/expenses/{e.id}", json={"project_code_id": k["pk"].id})
    db.refresh(e)
    assert e.kesz is False
