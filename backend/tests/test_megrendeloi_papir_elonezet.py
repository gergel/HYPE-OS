"""Megrendelői szerződés és TIG (projektkód oldala): ELŐNÉZET a "Generálás és
küldés" előtt (a felhasználó kérése, 2026-10) - pontosan az a levél és az a
kitöltött dokumentum, ami kimenne, de semmi nem mentődik és semmi nem megy ki.

A Google-dokumentum és a levélküldés le van cserélve (semmi nem megy ki).
Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import base64

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig
from app.models.project_code import ProjectCode

MP = "/api/v1/megrendeloi-papirok"


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

    admin = Employee(full_name="Megrendelői Admin (demó)", tipus=EmployeeType.BELSOS, email="mr-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    pk = ProjectCode(projektkod="MR-ELONEZET-DEMO", project_nev="Tavaszi kampányfilm (demó)")
    db.add_all([admin, pk])
    db.flush()

    kint = {"level": [], "doc": [], "elonezet": []}

    def level(to, subject, html, **kw):
        kint["level"].append({"to": to, "subject": subject, "html": html})
        return ("thr", "gm", "<rfc@x>")

    def doc(*, template_file_id, base_name, fields, output_folder_id=None):
        kint["doc"].append({"nev": base_name, "mezok": fields})
        return b"%PDF-kesz", "https://tarhely/demo.pdf"

    def elonezet_pdf(*, template_file_id, base_name, fields):
        kint["elonezet"].append({"sablon": template_file_id, "mezok": fields})
        return b"%PDF-elonezet"

    monkeypatch.setattr("app.api.routes.megrendeloi_papirok.send_message", level)
    monkeypatch.setattr("app.api.routes.megrendeloi_papirok.gdoc_fill_export_and_store_pdf", doc)
    monkeypatch.setattr("app.services.papir_elonezet.gdoc_elonezet_pdf", elonezet_pdf)
    monkeypatch.setattr(settings, "gdoc_megrendeloi_eseti_template_id", "sablon-mr-szerzodes")
    monkeypatch.setattr(settings, "gdoc_megrendeloi_tig_template_id", "sablon-mr-tig")

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "db": db, "pk": pk, "kint": kint}
    finally:
        app.dependency_overrides.clear()


ADAT = {"ceg_neve": "Megrendelő (demó) Kft.", "email": "megrendelo-demo@example.test", "netto_osszeg": 1_500_000,
        "projekt_nev": "Tavaszi kampányfilm (demó)", "teljesites_szoveg": "2026. október", "plusz_afa": True}


def test_szerzodes_elonezet_semmit_nem_ment_es_nem_kuld(k):
    c, pk, kint = k["c"], k["pk"], k["kint"]
    r = c.post(f"{MP}/szerzodes/{pk.id}/elonezet", json=ADAT)
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["cimzett"] == "megrendelo-demo@example.test"
    assert e["targy"] == "Tavaszi kampányfilm (demó) – megrendelői szerződés"
    assert "<b>Tavaszi kampányfilm (demó)</b>" in e["level_html"]
    assert base64.b64decode(e["pdf_base64"]) == b"%PDF-elonezet"
    mezok = kint["elonezet"][0]["mezok"]
    assert kint["elonezet"][0]["sablon"] == "sablon-mr-szerzodes"
    assert mezok["netto"] == "1 500 000" and mezok["afa"] == "+ ÁFA" and mezok["projektnev"] == "Tavaszi kampányfilm (demó)"
    assert mezok["kelt"]  # a keltezés a mai nap, ahogy a kiküldésnél
    # Semmi nem mentődött, semmi nem ment ki.
    assert k["db"].query(MegrendeloiSzerzodes).filter_by(project_code_id=pk.id).count() == 0
    assert kint["level"] == [] and kint["doc"] == []


def test_meglevo_tig_elonezete_a_beirt_adatokbol_es_nem_irja_at(k):
    c, pk, kint = k["c"], k["pk"], k["kint"]
    r = c.post(f"{MP}/tig/{pk.id}/mentes", json={**ADAT, "netto_osszeg": 1000})
    papir_id = r.json()["id"]
    e = c.post(f"{MP}/tig/{pk.id}/elonezet?papir_id={papir_id}", json=ADAT).json()
    assert e["targy"] == "Tavaszi kampányfilm (demó) – teljesítési igazolás"
    assert kint["elonezet"][-1]["mezok"]["projkod"] == "MR-ELONEZET-DEMO"
    assert kint["elonezet"][-1]["mezok"]["netto"] == "1 500 000"
    # A mentett papír nem változott, és csak levél-előnézet is kérhető.
    k["db"].expire_all()
    assert float(k["db"].get(MegrendeloiTig, papir_id).netto_osszeg) == 1000
    assert c.post(f"{MP}/tig/{pk.id}/elonezet?papir_id={papir_id}&pdf=false", json={}).json()["pdf_base64"] is None


def test_kuldes_ugyanazt_kuldi_mint_az_elonezet(k):
    c, pk, kint = k["c"], k["pk"], k["kint"]
    e = c.post(f"{MP}/szerzodes/{pk.id}/elonezet?pdf=false", json=ADAT).json()
    r = c.post(f"{MP}/szerzodes/{pk.id}/generalas-es-kuldes", json=ADAT)
    assert r.status_code == 200, r.text
    assert kint["level"][0]["subject"] == e["targy"] and kint["level"][0]["html"] == e["level_html"]
    assert kint["doc"][0]["nev"] == "MR-ELONEZET-DEMO_Megrendelő (demó) Kft._szerzodes"
    assert r.json()["allapot"] == "Kiküldve"


def test_sablon_nelkul_az_elonezet_megmondja_hogy_nem_kuldheto(k, monkeypatch):
    monkeypatch.setattr(settings, "gdoc_megrendeloi_eseti_template_id", "")
    e = k["c"].post(f"{MP}/szerzodes/{k['pk'].id}/elonezet", json=ADAT).json()
    assert e["pdf_base64"] is None and "nem is küldhető ki" in e["pdf_hiba"]


def test_atirt_level_megy_ki_es_megmarad_ures_az_alap(k):
    """Kapcsolóval átírható levél (a felhasználó kérése): az előnézet és a
    küldés is az átírttal megy; üresen (vagy átírás nélkül) az alap levél."""
    c, pk, kint = k["c"], k["pk"], k["kint"]
    e = c.post(f"{MP}/szerzodes/{pk.id}/elonezet?pdf=false", json={"projekt_nev": "Tavaszi kampányfilm (demó)"}).json()
    assert e["alap_szoveg"].startswith("Kedves Partnerünk!") and "Tavaszi kampányfilm (demó)" in e["alap_szoveg"]
    assert e["alap_targy"] == "Tavaszi kampányfilm (demó) – megrendelői szerződés"

    sajat = "Kedves Anna!\n\nCsatolva a szerződés <aláírásra>.\n\nÜdv,\nHYPE"
    r = c.post(f"{MP}/szerzodes/{pk.id}/mentes", json={**ADAT, "email_targy": "Szerződés – tavasz", "email_szoveg": sajat})
    papir = r.json()
    assert papir["email_szoveg"] == sajat and papir["email_targy"] == "Szerződés – tavasz"

    e = c.post(f"{MP}/szerzodes/{pk.id}/elonezet?papir_id={papir['id']}&pdf=false", json={}).json()
    assert e["targy"] == "Szerződés – tavasz" and "<p>Kedves Anna!</p>" in e["level_html"]
    assert "&lt;aláírásra&gt;" in e["level_html"] and "Rahman Martin" not in e["level_html"]

    r = c.post(f"{MP}/szerzodes/{pk.id}/generalas-es-kuldes?papir_id={papir['id']}", json={})
    assert r.status_code == 200, r.text
    assert kint["level"][-1]["subject"] == "Szerződés – tavasz" and "<p>Kedves Anna!</p>" in kint["level"][-1]["html"]


def test_kikapcsolva_ures_szoveg_az_alap_levelet_kuldi(k):
    from app.api.routes.megrendeloi_papirok import _EMAIL_HTML

    c, pk, kint = k["c"], k["pk"], k["kint"]
    r = c.post(f"{MP}/tig/{pk.id}/mentes", json={**ADAT, "email_szoveg": "Átírt", "email_targy": "X"})
    papir_id = r.json()["id"]
    # A kapcsoló kikapcsolása üres szövegeket küld -> vissza az alapra.
    r = c.post(f"{MP}/tig/{pk.id}/generalas-es-kuldes?papir_id={papir_id}", json={"email_szoveg": "", "email_targy": " "})
    assert r.status_code == 200, r.text
    assert r.json()["email_szoveg"] is None and r.json()["email_targy"] is None
    assert kint["level"][-1]["html"] == _EMAIL_HTML.format(projekt="Tavaszi kampányfilm (demó)", papir="teljesítési igazolás")
    assert kint["level"][-1]["subject"] == "Tavaszi kampányfilm (demó) – teljesítési igazolás"
