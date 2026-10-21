"""Külsős TIG: CSAK GENERÁLÁS, kiküldés nélkül (a felhasználó kérése, 2026-10).

Az utókövetésben lehessen csak legenerálni a TIG-et: elkészül, felkerül a
rendszerbe (kész állapot, jöhet a számla), de e-mail NEM megy ki - a
generálás és küldés mellette változatlan. Forgatásos és projektkódos ágon is.

A Google-dokumentum és a levélküldés le van cserélve (semmi nem megy ki).
Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.admin_ellenorzes import AdminTevekenyseg
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.models.project_code import ProjectCode

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

    admin = Employee(full_name="Generáló Admin (demó)", tipus=EmployeeType.BELSOS, email="gen-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Generált Hangos (demó)", tipus=EmployeeType.KULSOS,
                      email="gen-hangos-demo@example.test", is_active=True)
    p = Project(nev="Generálós forgatás (demó)", forgatas_datuma=date(2026, 10, 6))
    pk = ProjectCode(projektkod="GEN-DEMO-PK", project_nev="Generálós tanácsadás (demó)")
    db.add_all([admin, kulsos, p, pk])
    db.flush()
    p.crew.append(kulsos)
    db.add(Expense(megnevezes="Tanácsadás (demó)", netto=50000, brutto=50000, tipus="kulsos",
                   project_code_id=pk.id, employee_id=kulsos.id))
    db.flush()
    db.refresh(pk)

    kint = {"level": [], "doc": []}

    def level(to, subject, html, **kw):
        kint["level"].append({"to": to, "subject": subject})
        return ("thr", "gm", "<rfc@x>")

    def doc(*, template_file_id, base_name, fields, output_folder_id=None):
        kint["doc"].append({"nev": base_name, "mezok": fields})
        return b"%PDF-kesz", f"doc-{len(kint['doc'])}"

    for modul in ("subcontractor_contracts", "performance_certificates"):
        monkeypatch.setattr(f"app.api.routes.{modul}.send_message", level)
        monkeypatch.setattr(f"app.api.routes.{modul}.gdoc_fill_and_export_pdf", doc)
    monkeypatch.setattr(settings, "gdoc_alvallalkozoi_szerzodes_template_id", "sablon-szerzodes")
    monkeypatch.setattr(settings, "gdoc_kulsos_tig_template_id", "sablon-tig")

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "db": db, "kulsos": kulsos, "p": p, "pk": pk, "kulcs": f"e{kulsos.id}",
               "kint": kint}
    finally:
        app.dependency_overrides.clear()


def _tig(k) -> PerformanceCertificate:
    return k["db"].query(PerformanceCertificate).filter(PerformanceCertificate.employee_id == k["kulsos"].id).one()


def test_forgatasos_tig_csak_generalas_nem_kuld_levelet(k):
    c, p, kulcs, kint = k["c"], k["p"], k["kulcs"], k["kint"]
    assert c.post(f"{SZ}/{p.id}/{kulcs}/generate-and-send", json={"netto_osszeg": 50000}).status_code == 200
    levelek_elotte = len(kint["level"])

    r = c.post(f"{TIG}/{p.id}/{kulcs}/generalas", json={"netto_osszeg": 50000, "teljesites_szoveg": "2026.10.06."})
    assert r.status_code == 200, r.text
    assert r.json()["csak_generalva"] is True and r.json()["allapot"] == "Kiküldve"
    assert len(kint["level"]) == levelek_elotte  # levél NEM ment ki
    assert kint["doc"][-1]["mezok"]["tido"] == "2026.10.06."
    tig = _tig(k)
    assert tig.file_url == f"https://docs.google.com/document/d/doc-{len(kint['doc'])}/edit"
    # A projekten már nincs hátra TIG (kész), és a naplóban "generálva" lépés.
    assert c.get(f"{TIG}/{p.id}").json()["pending"] == []
    sor = k["db"].query(AdminTevekenyseg).filter_by(muvelet="generalas").one()
    assert sor.leiras == "Külsős TIG: legenerálva, kiküldés nélkül"
    # A Külsős TIG-ek listája is mutatja, hogy nem ment ki.
    lista = c.get("/api/v1/kulsos-tigek").json()
    assert any(t["id"] == tig.id and t["csak_generalva"] for t in (lista if isinstance(lista, list) else lista["tigek"]))


def test_generalas_es_kuldes_valtozatlan(k):
    c, p, kulcs, kint = k["c"], k["p"], k["kulcs"], k["kint"]
    c.post(f"{SZ}/{p.id}/{kulcs}/generate-and-send", json={"netto_osszeg": 50000})
    r = c.post(f"{TIG}/{p.id}/{kulcs}/generate-and-send", json={"netto_osszeg": 50000})
    assert r.status_code == 200, r.text
    assert r.json()["csak_generalva"] is False
    assert kint["level"][-1]["to"] == ["gen-hangos-demo@example.test"]


def test_sablon_nelkul_nincs_mit_generalni(k, monkeypatch):
    c, p, kulcs = k["c"], k["p"], k["kulcs"]
    c.post(f"{SZ}/{p.id}/{kulcs}/generate-and-send", json={"netto_osszeg": 50000})
    monkeypatch.setattr(settings, "gdoc_kulsos_tig_template_id", "")
    r = c.post(f"{TIG}/{p.id}/{kulcs}/generalas", json={"netto_osszeg": 50000})
    assert r.status_code == 400 and "sablon" in r.json()["detail"]
    assert _tig(k).allapot == "Készítés alatt"


def test_projektkodos_tig_csak_generalas(k):
    c, pk, kulcs, kint = k["c"], k["pk"], k["kulcs"], k["kint"]
    assert c.post(f"{SZ}/projektkodok/{pk.id}/{kulcs}/generate-and-send",
                  json={"netto_osszeg": 50000}).status_code == 200
    levelek_elotte = len(kint["level"])
    r = c.post(f"{TIG}/projektkodok/{pk.id}/{kulcs}/generalas", json={"netto_osszeg": 50000})
    assert r.status_code == 200, r.text
    assert r.json()["csak_generalva"] is True and r.json()["allapot"] == "Kiküldve"
    assert len(kint["level"]) == levelek_elotte
    assert kint["doc"][-1]["nev"] == "GEN-DEMO-PK_Generált Hangos (demó)_TIG"
