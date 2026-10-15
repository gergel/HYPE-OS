"""Érthető hibaüzenetek a semmitmondó "Váratlan szerverhiba" helyett (a
felhasználó jelezte: a diszpó nem ment ki, és a projekt mezői sem mentődtek,
de a felületen semmi nem derült ki az okáról).

Tranzakcióban / külön kapcsolatokon fut a helyi adatbázison, és a végén
VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.project import Project
from app.services import hiba_forditas


def test_zarolt_sor_es_google_hibak_forditasa():
    # Valódi zárolás: az egyik kapcsolat fogja a zárat, a másik rövid
    # lock_timeout-tal próbálja - pont az a hiba, ami élesben 15 mp után jön.
    with engine.connect() as fogo, engine.connect() as varo:
        tx = fogo.begin()
        fogo.execute(text("SELECT pg_advisory_xact_lock(4242001)"))
        tx2 = varo.begin()
        varo.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(OperationalError) as hiba:
            varo.execute(text("SELECT pg_advisory_xact_lock(4242001)"))
        tx2.rollback()
        tx.rollback()
    f = hiba_forditas.fordit(hiba.value)
    assert f is not None and f.status_code == 409 and "másik, még futó művelet" in f.detail
    # Egy RuntimeError mögé csomagolva is megtalálja.
    try:
        raise RuntimeError("csomagolás") from hiba.value
    except RuntimeError as csomagolt:
        assert hiba_forditas.fordit(csomagolt).status_code == 409

    from google.auth.exceptions import RefreshError
    from googleapiclient.errors import HttpError

    g = hiba_forditas.fordit(RefreshError("invalid_grant: Token has been expired or revoked."))
    assert g.status_code == 503 and "Google-fiók hozzáférése" in g.detail and "invalid_grant" not in g.detail
    resp = type("R", (), {"status": 403, "reason": "Forbidden"})()
    assert hiba_forditas.fordit(HttpError(resp, b"{}")).status_code == 502
    assert hiba_forditas.fordit(KeyError("x")) is None
    assert hiba_forditas.ismeretlen_uzenet(KeyError("x")) == "Váratlan szerverhiba történt (KeyError)."


@pytest.fixture
def k(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    with engine.connect() as conn:
        tx = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        admin = Employee(full_name="Hibaüzenet Admin (demó)", tipus=EmployeeType.BELSOS,
                         email="hibauzenet-demo@example.test", role=SystemRole.ADMIN, is_active=True)
        p = Project(nev="Hibaüzenet próba (demó)")
        db.add_all([admin, p])
        db.flush()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: admin
        db.commit = db.flush
        try:
            yield {"c": TestClient(app), "p": p}
        finally:
            app.dependency_overrides.clear()
            db.close()
            tx.rollback()


def test_lejart_google_hozzaferes_a_diszpo_kuldesnel_erthetoen_jelez(k, monkeypatch):
    from google.auth.exceptions import RefreshError

    from app.api.routes import projects

    def lejart(*_a, **_k):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(projects, "send_elozetes_diszpo", lejart)
    r = k["c"].post(f"/api/v1/projects/{k['p'].id}/diszpo/elozetes")
    assert r.status_code == 503
    assert "Google-fiók hozzáférése lejárt" in r.json()["detail"] and "NEM ment ki" in r.json()["detail"]

    monkeypatch.setattr(projects, "send_elozetes_diszpo", lambda *a, **kw: {}["nincs"])
    r = k["c"].post(f"/api/v1/projects/{k['p'].id}/diszpo/elozetes")
    assert r.status_code == 500 and r.json()["detail"] == "Váratlan szerverhiba történt (KeyError)."
