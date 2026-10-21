"""Még ki nem fizetett kiadás felvezetése és a "Kifizetésre vár" fül (a
felhasználó kérése, 2026-10): a Kiadásoknál "Még nem (számla jött)" +
fizetési határidő; az egyenlegekbe csak kifizetve számít; a "Fizetés" gomb
(dátummal) teszi kifizetetté. Plusz az AI-kiolvasás az Autóknál.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.notion_import import NotionImportMap
from app.models.performance_certificate import PerformanceCertificate
from app.services import kiadas_kiolvasas

MA = date.today()


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
def c(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Váró Admin (demó)", tipus=EmployeeType.BELSOS, email="varo-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    db.add(admin)
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _osszegzes(c):
    s = c.get("/api/v1/finance/summary").json()
    return s["ytd_kiadas"], s["szamla_ki"]


def test_kifizetetlen_kiadas_a_varo_fulon_es_csak_fizetes_utan_szamit(db, c):
    elotte = _osszegzes(c)
    hatarido = (MA + timedelta(days=10)).isoformat()
    # A Kiadások űrlapja így küldi: kesz "false" + határidő, fizetés dátuma nélkül.
    r = c.post("/api/v1/expenses", json={"megnevezes": "Szerviz Kft. (demó)", "kiadas_leiras": "Javítás (demó)",
                                         "netto": 123_457, "kifizetes_modja": "Átutalás", "tipus": "egyeb",
                                         "kesz": "false", "fizetes_hatarideje": hatarido})
    assert r.status_code == 201, r.text
    e = db.get(Expense, r.json()["id"])
    assert not e.kesz and e.fizetes_datuma is None
    assert e.id in c.get("/api/v1/finance/kifizetesre-varo-kiadasok").json()
    assert any(t["kulcs"] == f"kiadas:{e.id}" and t["hatarido"] == hatarido
               for t in c.get("/api/v1/finance/utalasra-varo").json())
    # Az egyenlegekből (idei kiadás, számla-egyenleg) még NEM vonódik le.
    assert _osszegzes(c) == elotte

    # Fizetés gomb: kesz + fizetés dátuma -> lekerül a fülről, beleszámít.
    c.patch(f"/api/v1/expenses/{e.id}", json={"kesz": True, "fizetes_datuma": MA.isoformat()})
    assert e.id not in c.get("/api/v1/finance/kifizetesre-varo-kiadasok").json()
    utana = _osszegzes(c)
    assert utana[0] == pytest.approx(elotte[0] + 123_457)
    assert utana[1] == pytest.approx(elotte[1] + 123_457)


def test_kifizetettkent_felvitt_kiadas_kesz_alvallalkozosan_is(db, c):
    r = c.post("/api/v1/expenses", json={"megnevezes": "Kész Bt. (demó)", "netto": 2_345, "kifizetes_modja": "Átutalás",
                                         "tipus": "kulsos", "kesz": "true", "fizetes_datuma": MA.isoformat()})
    assert r.status_code == 201, r.text
    assert db.get(Expense, r.json()["id"]).kesz is True


def test_regi_notion_es_tig_sor_nem_kerul_a_varo_fulre(db, c):
    notionos = Expense(megnevezes="Adobe (demó)", netto=1000, tipus="egyeb")
    notionos_hataridos = Expense(megnevezes="Régi számla (demó)", netto=1000, tipus="egyeb",
                                 fizetes_hatarideje=MA + timedelta(days=3))
    tiges = Expense(megnevezes="TIG kiadás (demó)", netto=1000, tipus="kulsos")
    projektkodos = Expense(megnevezes="Vonatjegy (demó)", netto=1000, tipus="egyeb")
    db.add_all([notionos, notionos_hataridos, tiges, projektkodos])
    db.flush()
    db.add_all([
        NotionImportMap(notion_page_id="demo-notion-1", entity_type="Expense", entity_id=notionos.id),
        NotionImportMap(notion_page_id="demo-notion-2", entity_type="Expense", entity_id=notionos_hataridos.id),
    ])
    kulsos = Employee(full_name="TIG Külsős (demó)", tipus=EmployeeType.KULSOS, is_active=True)
    db.add(kulsos)
    db.flush()
    db.add(PerformanceCertificate(employee_id=kulsos.id, expense_id=tiges.id))
    db.flush()
    varo = set(c.get("/api/v1/finance/kifizetesre-varo-kiadasok").json())
    assert notionos.id not in varo and tiges.id not in varo
    assert notionos_hataridos.id in varo and projektkodos.id in varo


def test_ai_kifizetettseg_javaslat():
    jovo = (MA + timedelta(days=5)).isoformat()
    a = {"fizetes_hatarideje": jovo, "kifizetes_modja": "Átutalás"}
    kiadas_kiolvasas.kifizetettseg_javaslat(a, MA)
    assert a["kesz"] == "false"
    for adat in ({"fizetes_hatarideje": jovo, "kifizetes_modja": "Bankkártya"},
                 {"fizetes_hatarideje": (MA - timedelta(days=5)).isoformat()},
                 {"fizetes_hatarideje": None}):
        kiadas_kiolvasas.kifizetettseg_javaslat(adat, MA)
        assert "kesz" not in adat
    rossz = {"fizetes_hatarideje": "nem dátum"}
    kiadas_kiolvasas.kifizetettseg_javaslat(rossz, MA)
    assert rossz["fizetes_hatarideje"] is None


def test_autos_ai_kiolvasas_vegpont(c, monkeypatch):
    jovo = (MA + timedelta(days=8)).isoformat()
    monkeypatch.setattr(kiadas_kiolvasas, "olvasd_ki", lambda adat, mime: {
        "megnevezes": "Szerviz Kft. (demó)", "kiadas_leiras": "Fékbetét csere", "netto": 80000,
        "plusz_afa": "igen", "fizetes_hatarideje": jovo, "kifizetes_modja": "Átutalás"})
    r = c.post("/api/v1/autok/kiadasok/kiolvasas", files={"file": ("szamla.pdf", b"%PDF-1.4 demo", "application/pdf")})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["kiadas_leiras"] == "Fékbetét csere" and v["kesz"] == "false" and v["fizetes_hatarideje"] == jovo
    r = c.post("/api/v1/autok/kiadasok/kiolvasas", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400
