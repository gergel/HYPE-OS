"""Összevont (10-20 projektes) szerződés/TIG (a felhasználó hibajelzése,
2026-10): ami az Utókövetésben "nincs szerződése" teendőként látszik, annak a
szerződésre és a TIG-re PIPÁLHATÓNAK is kell lennie. Korábban a pipálható lista
csak a diszpózott projekteket hozta, így kimaradt az a forgatás, amit csak
alvállalkozói kiadás köt - és ott a szerződés után is "nincs szerződése" maradt.

A levélküldés és a Google-dokumentum le van cserélve. Tranzakcióban fut a helyi
adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.project import Project

SZ = "/api/v1/alvallalkozoi-szerzodesek"
TIG = "/api/v1/teljesitesi-igazolasok"


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
def k(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Pipálható Admin (demó)", tipus=EmployeeType.BELSOS, email="pip-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Pipálható Operatőr (demó)", tipus=EmployeeType.KULSOS,
                      email="pip-operator-demo@example.test", is_active=True)
    # 12 diszpózott (stábos) forgatás + egy, amit csak alvállalkozói kiadás köt.
    stabos = [Project(nev=f"Őszi forgatás {i + 1} (demó)", forgatas_datuma=date(2026, 9, 1 + i)) for i in range(12)]
    kiadasos = Project(nev="Csak kiadásos forgatás (demó)", forgatas_datuma=date(2026, 5, 10))
    db.add_all([admin, kulsos, *stabos, kiadasos])
    db.flush()
    for p in stabos:
        p.crew.append(kulsos)
    db.add(Expense(megnevezes="Plusz munka (demó)", netto=10000, tipus="kulsos", employee_id=kulsos.id,
                   alvallalkozo_project_id=kiadasos.id))
    db.flush()
    for modul in ("subcontractor_contracts", "performance_certificates"):
        monkeypatch.setattr(f"app.api.routes.{modul}.send_message", lambda *a, **kw: ("t", "g", "<r>"))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "kulsos": kulsos, "stabos": stabos, "kiadasos": kiadasos, "kulcs": f"e{kulsos.id}"}
    finally:
        app.dependency_overrides.clear()


def test_ami_a_listan_teendo_az_pipalhato_es_lefedheto(k):
    c, kulcs, mind = k["c"], k["kulcs"], [*k["stabos"], k["kiadasos"]]
    lista = {x["project_id"] for x in c.get(SZ).json()}
    assert {p.id for p in mind} <= lista

    nyitott = c.get(f"{SZ}/{k['stabos'][0].id}/{kulcs}/nyitott-tetelek").json()
    assert {t["project_id"] for t in nyitott} >= {p.id for p in mind}

    tetelek = [{"project_id": p.id, "employee_id": k["kulsos"].id} for p in mind]
    r = c.post(f"{SZ}/{k['stabos'][0].id}/{kulcs}/generate-and-send", json={"tetelek": tetelek, "netto_osszeg": 650000})
    assert r.status_code == 200, r.text
    # Egyik projekten sem marad "nincs szerződése" teendő - a kiadásoson sem.
    for p in mind:
        assert c.get(f"{SZ}/{p.id}").json()["pending"] == [], p.nev
    assert not {x["project_id"] for x in c.get(SZ).json()} & {p.id for p in mind}

    # A TIG-re is mind pipálható.
    tig_nyitott = c.get(f"{TIG}/{k['stabos'][0].id}/{kulcs}/nyitott-tetelek").json()
    assert {t["project_id"] for t in tig_nyitott} >= {p.id for p in mind}
