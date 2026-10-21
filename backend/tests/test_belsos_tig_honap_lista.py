"""Belsős TIG havi lista (a felhasználó jelezte, 2026-10): a havi áttekintés
hiányzóként mutatott valakit ("Készítés alatt"), a hónap megnyitásakor viszont
sehol nem volt - mert a felvitt belsős időszaka nem fedte le a hónapot. Akinek
erre a hónapra VAN bejegyzése, annak a hónap listáján is ott kell lennie, hogy
be lehessen fejezni.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.internal_performance_certificate import InternalPerformanceCertificate as Tig

EV, HO = 2031, 6  # jövőbeli hónap: az élő adatokkal nem ütközik


@pytest.fixture
def k(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    with engine.connect() as conn:
        tx = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        admin = Employee(full_name="Havi Lista Admin (demó)", tipus=EmployeeType.BELSOS,
                         email="havi-lista-demo@example.test", role=SystemRole.ADMIN, is_active=True)
        # Az időszaka júliusban kezdődik, de júniusra már van félkész TIG-je.
        csuszott = Employee(full_name="Ábel Elcsúszott (demó)", tipus=EmployeeType.BELSOS, is_active=True)
        rendes = Employee(full_name="Zoltán Rendes (demó)", tipus=EmployeeType.BELSOS, is_active=True)
        kulsos = Employee(full_name="Külsős Bejegyzéssel (demó)", tipus=EmployeeType.KULSOS, is_active=True)
        db.add_all([admin, csuszott, rendes, kulsos])
        db.flush()
        db.add_all([
            BelsosIdoszak(employee_id=csuszott.id, kezdet=date(EV, 7, 1)),
            BelsosIdoszak(employee_id=rendes.id, kezdet=date(EV, 1, 1)),
            BelsosIdoszak(employee_id=admin.id, kezdet=date(EV + 5, 1, 1)),
            Tig(employee_id=csuszott.id, ev=EV, honap=HO, allapot="Készítés alatt"),
            Tig(employee_id=kulsos.id, ev=EV, honap=HO, allapot="Készítés alatt"),
        ])
        db.flush()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: admin
        db.commit = db.flush
        try:
            yield {"c": TestClient(app), "csuszott": csuszott, "rendes": rendes, "kulsos": kulsos}
        finally:
            app.dependency_overrides.clear()
            db.close()
            tx.rollback()


def test_bejegyzessel_rendelkezo_belsos_a_honap_listajan_is_ott_van(k):
    c = k["c"]
    lista = c.get(f"/api/v1/belsos-tig?ev={EV}&honap={HO}").json()
    nevek = {e["id"]: e for e in lista}
    assert k["csuszott"].id in nevek and nevek[k["csuszott"].id]["record"]["allapot"] == "Készítés alatt"
    assert k["rendes"].id in nevek
    # Külsőshöz tartozó (importból maradt) bejegyzés nem hoz be senkit.
    assert k["kulsos"].id not in nevek
    # Névsor ékezettől függetlenül: "Ábel" elöl, "Zoltán" a végén.
    sajat = [e["id"] for e in lista if e["id"] in (k["csuszott"].id, k["rendes"].id)]
    assert sajat == [k["csuszott"].id, k["rendes"].id]

    # Az áttekintés ugyanazt mutatja hiányzónak, amit a lista tartalmaz.
    honap = next(h for h in c.get("/api/v1/belsos-tig/attekintes").json() if (h["ev"], h["honap"]) == (EV, HO))
    hianyzok = {t["employee_id"] for t in honap["teendok"]}
    assert k["csuszott"].id in hianyzok and hianyzok <= set(nevek)

    # Ott be is lehet fejezni (pl. kézzel kiküldöttnek jelölni).
    r = c.post(f"/api/v1/belsos-tig/{k['csuszott'].id}/{EV}/{HO}/allapot", json={"allapot": "Kiküldve"})
    assert r.status_code == 200, r.text
