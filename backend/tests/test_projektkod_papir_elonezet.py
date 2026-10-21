"""Projektkódos (forgatás nélküli) alvállalkozói szerződés és külsős TIG:
kiküldés előtti ELŐNÉZET a papírra és a levélre, és a levél ÁTÍRHATÓ (a
felhasználó kérése, 2026-10) - ugyanúgy, mint a forgatásos ágon.

- Az előnézet semmit nem ment és semmit nem küld.
- Az átírt tárgy és szöveg a kiküldésnél is azzal megy ki (alatta mindig a
  közös aláírás), és a piszkozaton megmarad.
- Átírás nélkül pontosan az eddigi alap levél megy.

A Google-dokumentum és a levélküldés le van cserélve (semmi nem megy ki).
Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import base64

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.contract import Contract, ContractType
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate
from app.models.project_code import ProjectCode

SZ = "/api/v1/alvallalkozoi-szerzodesek/projektkodok"
TIG = "/api/v1/teljesitesi-igazolasok/projektkodok"


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

    admin = Employee(full_name="Projektkód Admin (demó)", tipus=EmployeeType.BELSOS, email="pk-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Projektkód Tanácsadó (demó)", tipus=EmployeeType.KULSOS,
                      email="pk-tanacsado-demo@example.test", is_active=True)
    pk = ProjectCode(projektkod="PK-ELONEZET-DEMO", project_nev="Tanácsadás (demó)")
    db.add_all([admin, kulsos, pk])
    db.flush()
    # Forgatás nélküli, külsős besorolású kiadás -> kell szerződés és TIG.
    db.add(Expense(megnevezes="Tanácsadás (demó)", netto=80000, brutto=80000, tipus="kulsos",
                   project_code_id=pk.id, employee_id=kulsos.id))
    db.flush()
    db.refresh(pk)

    kint = {"level": [], "doc": [], "elonezet": []}

    def level(to, subject, html, **kw):
        kint["level"].append({"to": to, "subject": subject, "html": html})
        return ("thr", "gm", "<rfc@x>")

    def doc(*, template_file_id, base_name, fields, output_folder_id=None):
        kint["doc"].append({"nev": base_name, "mezok": fields})
        return b"%PDF-kesz", f"doc-{len(kint['doc'])}"

    def elonezet_pdf(*, template_file_id, base_name, fields):
        kint["elonezet"].append({"nev": base_name, "mezok": fields})
        return b"%PDF-elonezet"

    for modul in ("subcontractor_contracts", "performance_certificates"):
        monkeypatch.setattr(f"app.api.routes.{modul}.send_message", level)
        monkeypatch.setattr(f"app.api.routes.{modul}.gdoc_fill_and_export_pdf", doc)
    monkeypatch.setattr("app.services.papir_elonezet.gdoc_elonezet_pdf", elonezet_pdf)
    monkeypatch.setattr(settings, "gdoc_alvallalkozoi_szerzodes_template_id", "sablon-szerzodes")
    monkeypatch.setattr(settings, "gdoc_kulsos_tig_template_id", "sablon-tig")

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "db": db, "kulsos": kulsos, "pk": pk, "kulcs": f"e{kulsos.id}", "kint": kint}
    finally:
        app.dependency_overrides.clear()


def _szerzodesek(k):
    return k["db"].query(Contract).filter(Contract.employee_id == k["kulsos"].id,
                                          Contract.tipus == ContractType.ALVALLALKOZOI).all()


def test_szerzodes_elonezet_semmit_nem_ment_es_nem_kuld(k):
    c, pk, kulcs, kint = k["c"], k["pk"], k["kulcs"], k["kint"]
    r = c.post(f"{SZ}/{pk.id}/{kulcs}/elonezet", json={"netto_osszeg": 80000, "teljesites_szoveg": "2026. október"})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["cimzett"] == "pk-tanacsado-demo@example.test"
    assert e["targy"] == e["alap_targy"] == "PK-ELONEZET-DEMO_Projektkód Tanácsadó (demó)_szerződés"
    assert "Levelemhez csatoltan" in e["level_html"] and "Rahman Martin" in e["level_html"]
    assert e["szoveg"] == e["alap_szoveg"] and e["alap_szoveg"].startswith("Kedves Címzett,")
    assert base64.b64decode(e["pdf_base64"]) == b"%PDF-elonezet"
    mezok = kint["elonezet"][0]["mezok"]
    assert mezok["netto"] == "80 000" and mezok["tido"] == "2026. október" and mezok["projektnev"] == "Tanácsadás (demó)"
    # Semmi nem mentődött, semmi nem ment ki.
    assert _szerzodesek(k) == [] and kint["level"] == [] and kint["doc"] == []
    assert c.post(f"{SZ}/{pk.id}/{kulcs}/elonezet?pdf=false", json={}).json()["pdf_base64"] is None


def test_szerzodes_atirt_levellel_megy_ki_es_megmarad(k):
    c, pk, kulcs, kint = k["c"], k["pk"], k["kulcs"], k["kint"]
    sajat = "Szia Péter,\n\nCsatolom a szerződést <aláírásra>.\nKöszi!"
    r = c.post(f"{SZ}/{pk.id}/{kulcs}/elonezet?pdf=false",
               json={"email_targy": "Szerződés – októberi tanácsadás", "email_szoveg": sajat})
    e = r.json()
    assert e["targy"] == "Szerződés – októberi tanácsadás" and e["szoveg"] == sajat
    assert "<p>Szia Péter,</p>" in e["level_html"] and "&lt;aláírásra&gt;" in e["level_html"]
    assert "Levelemhez csatoltan" not in e["level_html"] and "Rahman Martin" in e["level_html"]

    # Mentés: a piszkozaton megmarad, és a következő megnyitáskor visszajön.
    assert c.post(f"{SZ}/{pk.id}/{kulcs}/save", json={"netto_osszeg": 80000, "email_szoveg": sajat}).status_code == 200
    draft = c.get(f"{SZ}/{pk.id}").json()["pending"][0]["draft"]
    assert draft["email_szoveg"] == sajat

    r = c.post(f"{SZ}/{pk.id}/{kulcs}/generate-and-send",
               json={"netto_osszeg": 80000, "email_targy": "Szerződés – októberi tanácsadás"})
    assert r.status_code == 200, r.text
    level = kint["level"][0]
    assert level["subject"] == "Szerződés – októberi tanácsadás" and "<p>Szia Péter,</p>" in level["html"]
    szerz = _szerzodesek(k)[0]
    assert szerz.szerzodes_allapota == "Kiküldve" and szerz.kikuldott_targy == "Szerződés – októberi tanácsadás"


def test_szerzodes_atiras_nelkul_az_eddigi_level_megy(k):
    from app.api.routes.subcontractor_contracts import _CONTRACT_EMAIL_HTML

    c, pk, kulcs, kint = k["c"], k["pk"], k["kulcs"], k["kint"]
    # Üres szöveg = vissza az alapra.
    r = c.post(f"{SZ}/{pk.id}/{kulcs}/generate-and-send", json={"netto_osszeg": 80000, "email_szoveg": "  "})
    assert r.status_code == 200, r.text
    assert kint["level"][0]["html"] == _CONTRACT_EMAIL_HTML
    assert kint["level"][0]["subject"] == "PK-ELONEZET-DEMO_Projektkód Tanácsadó (demó)_szerződés"
    assert kint["doc"][0]["nev"] == "PK-ELONEZET-DEMO_Projektkód Tanácsadó (demó)_szerződés"


def test_tig_elonezet_es_atirt_level(k):
    c, pk, kulcs, kint = k["c"], k["pk"], k["kulcs"], k["kint"]
    # TIG csak a szerződés után készülhet.
    assert c.post(f"{SZ}/{pk.id}/{kulcs}/generate-and-send", json={"netto_osszeg": 80000}).status_code == 200

    r = c.post(f"{TIG}/{pk.id}/{kulcs}/elonezet", json={"netto_osszeg": 80000, "teljesites_szoveg": "2026. október"})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["targy"] == "Projektkód Tanácsadó (demó)_PK-ELONEZET-DEMO - Projekt_TIG"
    assert "<b>2026. október</b>" in e["level_html"]
    assert "Alább a 2026. október dátumú" in e["alap_szoveg"]
    assert base64.b64decode(e["pdf_base64"]) == b"%PDF-elonezet"
    assert kint["elonezet"][-1]["mezok"]["projkod"] == "PK-ELONEZET-DEMO"
    tigek = k["db"].query(PerformanceCertificate).filter(PerformanceCertificate.employee_id == k["kulsos"].id).all()
    assert tigek == []  # az előnézet nem hozott létre piszkozatot

    r = c.post(f"{TIG}/{pk.id}/{kulcs}/generate-and-send",
               json={"netto_osszeg": 80000, "teljesites_szoveg": "2026. október",
                     "email_targy": "TIG – október", "email_szoveg": "Szia,\n\nItt a TIG."})
    assert r.status_code == 200, r.text
    level = kint["level"][-1]
    assert level["subject"] == "TIG – október" and "<p>Itt a TIG.</p>" in level["html"]
    assert "Rahman Martin" in level["html"]
    tig = k["db"].get(PerformanceCertificate, r.json()["id"])
    assert tig.allapot == "Kiküldve" and tig.email_szoveg == "Szia,\n\nItt a TIG."
    assert kint["doc"][-1]["nev"] == "PK-ELONEZET-DEMO_Projektkód Tanácsadó (demó)_TIG"
