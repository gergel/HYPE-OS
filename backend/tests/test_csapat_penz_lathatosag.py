"""Csapat: pénz csak Pénzügy-joggal (a felhasználó kérése): aki látja a
Csapatot, de a Pénzügyhöz nincs joga, az ne lássa a vágók órabérét, a belsősök
napidíját és elszámolását - és ne is tudja átírni. A kitakarás a szerveren
történik.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.rate import Rate
from app.models.user_access import PageAccessConfig

A = "/api/v1/crew"
R = "/api/v1/rates"
TELJES = ["view", "edit", "create", "delete"]


@pytest.fixture
def k():
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    with engine.connect() as conn:
        tx = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        csak_csapat = Employee(full_name="Csak Csapat (demó)", tipus=EmployeeType.BELSOS, role=SystemRole.ADMIN,
                               email="csak-csapat-demo@example.test", is_active=True)
        penzugyes = Employee(full_name="Pénzügyes (demó)", tipus=EmployeeType.BELSOS, role=SystemRole.ADMIN,
                             email="penzugyes-demo@example.test", is_active=True)
        belsos = Employee(full_name="Napidíjas Belsős (demó)", tipus=EmployeeType.BELSOS, napi_dij=40_000,
                          szerzodott_napok=12, plusz_nap_napi_dij=50_000, telefon="+36 1 234 5678", is_active=True)
        db.add_all([csak_csapat, penzugyes, belsos])
        db.flush()
        vago_ber = Rate(employee_id=belsos.id, orabler=6_000, nev="Vágás (demó)")
        db.add_all([
            vago_ber,
            PageAccessConfig(employee_id=csak_csapat.id, page_permissions={"/csapat": TELJES}),
            PageAccessConfig(employee_id=penzugyes.id, page_permissions={"/csapat": TELJES, "/penzugyek": TELJES}),
        ])
        db.flush()
        ki = {"user": csak_csapat}
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: ki["user"]
        db.commit = db.flush
        try:
            yield {"c": TestClient(app), "db": db, "ki": ki, "csak": csak_csapat, "penz": penzugyes,
                   "belsos": belsos, "ber": vago_ber}
        finally:
            app.dependency_overrides.clear()
            db.close()
            tx.rollback()


def test_penzugy_jog_nelkul_a_penz_kitakarva_es_nem_irhato(k):
    c, b = k["c"], k["belsos"]
    adat = c.get(f"{A}/{b.id}").json()
    assert adat["napi_dij"] is None and adat["szerzodott_napok"] is None and adat["plusz_nap_napi_dij"] is None
    assert adat["telefon"] == "+36 1 234 5678"  # a nem pénzes adat látszik
    lista = {e["id"]: e for e in c.get(A).json()}
    assert lista[b.id]["napi_dij"] is None
    ber = c.get(f"{R}/{k['ber'].id}").json()
    assert ber["orabler"] is None and ber["nev"] == "Vágás (demó)"

    # Írni sem lehet - de a pénzes mező üres visszaküldése nem akasztja meg
    # a többi mező mentését.
    assert c.patch(f"{A}/{b.id}", json={"napi_dij": 1}).status_code == 403
    r = c.patch(f"{A}/{b.id}", json={"telefon": "+36 9", "napi_dij": None})
    assert r.status_code == 200, r.text
    k["db"].refresh(b)
    assert float(b.napi_dij) == 40_000 and b.telefon == "+36 9"
    assert c.patch(f"{R}/{k['ber'].id}", json={"orabler": 1}).status_code == 403
    assert c.post(R, json={"employee_id": b.id, "orabler": 1}).status_code == 403
    assert c.delete(f"{R}/{k['ber'].id}").status_code == 403
    assert c.post(A, json={"full_name": "Új (demó)", "tipus": "belsos", "napi_dij": 5}).status_code == 403
    # A külsős elszámolás (mennyit fizettünk) üresen jön.
    assert c.get(f"{A}/{b.id}/munkak").json()["projektek"] == []


def test_penzugy_joggal_minden_latszik_es_irhato(k):
    c, b = k["c"], k["belsos"]
    k["ki"]["user"] = k["penz"]
    assert float(c.get(f"{A}/{b.id}").json()["napi_dij"]) == 40_000
    assert float(c.get(f"{R}/{k['ber'].id}").json()["orabler"]) == 6_000
    assert c.patch(f"{A}/{b.id}", json={"napi_dij": 45_000}).status_code == 200
    assert c.patch(f"{R}/{k['ber'].id}", json={"orabler": 6_500}).status_code == 200
