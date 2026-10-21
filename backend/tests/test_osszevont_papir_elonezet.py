"""Több projektre szóló alvállalkozói szerződés és külsős TIG (a felhasználó
kérése, 2026-10):

1. az összevont papír MINDEN kiválasztott projektnél "kész" és be van
   linkelve - akkor is, ha valamelyik projekten már volt félkész piszkozat
   (azt átveszi), és a külsős munkatárs adatlapján is minden projektnél;
2. kiküldés előtt ELŐNÉZET (levél + kitöltött dokumentum), ami semmit nem ment
   és semmit nem küld;
3. sok projektnél megadható, mi álljon a papíron a projektek felsorolása
   helyett, és mi legyen a levél tárgya - szerződésnél és TIG-nél is.

A Google-dokumentum és a levélküldés le van cserélve (semmi nem megy ki).
Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import base64
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.contract import Contract, ContractType
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.performance_certificate import PerformanceCertificate
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
    """Három forgatás ugyanazzal a külsőssel, egy kliens, és a lecserélt
    Google-dokumentum / levélküldés (ami kimenne, az a `kint` listákba kerül)."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = Employee(full_name="Összevont Admin (demó)", tipus=EmployeeType.BELSOS, email="ossz-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Összevont Operatőr (demó)", tipus=EmployeeType.KULSOS,
                      email="ossz-operator-demo@example.test", is_active=True)
    ps = [Project(nev=f"Szeptemberi forgatás {i + 1} (demó)", forgatas_datuma=date(2026, 9, 10 + i)) for i in range(3)]
    db.add_all([admin, kulsos, *ps])
    db.flush()
    for p in ps:
        p.crew.append(kulsos)
    db.flush()

    kint = {"level": [], "doc": [], "elonezet": []}

    def level(to, subject, html, **kw):
        kint["level"].append({"to": to, "subject": subject})
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
        yield {"c": TestClient(app), "db": db, "kulsos": kulsos, "ps": ps, "kulcs": f"e{kulsos.id}", "kint": kint}
    finally:
        app.dependency_overrides.clear()


def _tetelek(k, ps=None):
    return [{"project_id": p.id, "employee_id": k["kulsos"].id} for p in (ps or k["ps"])]


def _szerzodesek(k):
    return k["db"].query(Contract).filter(Contract.employee_id == k["kulsos"].id,
                                          Contract.tipus == ContractType.ALVALLALKOZOI).all()


def test_osszevont_szerzodes_atveszi_a_felkesz_piszkozatot_es_mindenhol_kesz(k):
    c, ps, kulcs = k["c"], k["ps"], k["kulcs"]
    # Valaki korábban a 2. forgatásról elkezdte és elmentette.
    r = c.post(f"{SZ}/{ps[1].id}/{kulcs}/save", json={"netto_osszeg": 40000})
    assert r.status_code == 200, r.text
    assert len(_szerzodesek(k)) == 1

    # Az 1. forgatásról egy szerződés mindhárom napra: eddig ütközési hibát adott.
    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/generate-and-send",
               json={"tetelek": _tetelek(k), "netto_osszeg": 120000, "ceg_neve": "Összevont Operatőr"})
    assert r.status_code == 200, r.text
    assert len(_szerzodesek(k)) == 1  # a kiürült piszkozat törlődött

    for p in ps:
        assert c.get(f"{SZ}/{p.id}").json()["pending"] == []
        osszes = c.get(f"{SZ}/{p.id}/all").json()
        assert len(osszes) == 1
        assert osszes[0]["szerzodes_allapota"] == "Kiküldve"
        assert osszes[0]["szerzodes_file_url"] == "https://docs.google.com/document/d/doc-1/edit"
        assert len(osszes[0]["projektek"]) == 3
        assert c.get(f"/api/v1/utokovetes/{p.id}").json()["szerzodes_fuggo"] == 0

    # A külsős adatlapján is mind a három forgatásnál ott a szerződés linkje, de
    # az összesítés a 120 000-et csak egyszer számolja.
    munkak = c.get(f"/api/v1/crew/{k['kulsos'].id}/munkak").json()
    sorok = {s["project_id"]: s for s in munkak["projektek"]}
    assert set(sorok) == {p.id for p in ps}
    for s in sorok.values():
        assert {"cimke": "Szerződés", "url": "https://docs.google.com/document/d/doc-1/edit"} in s["dokumentumok"]
    assert munkak["osszes_netto"] == 120000


def test_kikuldott_papir_tetele_tovabbra_is_utkozes(k):
    c, ps, kulcs = k["c"], k["ps"], k["kulcs"]
    r = c.post(f"{SZ}/{ps[1].id}/{kulcs}/generate-and-send", json={"netto_osszeg": 40000})
    assert r.status_code == 200, r.text
    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/generate-and-send", json={"tetelek": _tetelek(k), "netto_osszeg": 120000})
    assert r.status_code == 400
    assert "már szól egy másik szerződés" in r.json()["detail"]


def test_elonezet_semmit_nem_ment_es_nem_kuld(k):
    c, ps, kulcs, kint = k["c"], k["ps"], k["kulcs"], k["kint"]
    adat = {"tetelek": _tetelek(k), "netto_osszeg": 120000, "projekt_szoveg": "Szeptemberi forgatások",
            "email_targy": "Szeptemberi szerződés"}
    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/elonezet?pdf=false", json=adat)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["targy"] == "Szeptemberi szerződés"
    assert v["cimzett"] == "ossz-operator-demo@example.test"
    assert v["pdf_base64"] is None and kint["elonezet"] == []

    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/elonezet", json=adat)
    v = r.json()
    assert base64.b64decode(v["pdf_base64"]) == b"%PDF-elonezet"
    assert kint["elonezet"][0]["mezok"]["projektnev"] == "Szeptemberi forgatások"
    # Semmi nem mentődött és semmi nem ment ki.
    assert _szerzodesek(k) == []
    assert kint["level"] == [] and kint["doc"] == []

    # Sablon nélkül a levél előnézete megvan, a PDF helyett magyarázat jön.
    import app.core.config as cfg

    cfg.settings.gdoc_alvallalkozoi_szerzodes_template_id = ""
    v = c.post(f"{SZ}/{ps[0].id}/{kulcs}/elonezet", json=adat).json()
    assert v["pdf_base64"] is None and "sablon" in v["pdf_hiba"]


def test_egyedi_projekt_szoveg_es_targy_a_szerzodesen(k):
    c, ps, kulcs, kint = k["c"], k["ps"], k["kulcs"], k["kint"]
    # Alapból felsorolja a projekteket, a tárgy a régi minta.
    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/elonezet?pdf=true", json={"tetelek": _tetelek(k), "netto_osszeg": 1})
    mezok = kint["elonezet"][-1]["mezok"]
    assert all(p.nev in mezok["projektnev"] for p in ps)
    assert r.json()["targy"].endswith("_szerződés")

    # Mentve megmarad, és a kiküldésnél ez megy ki.
    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/save", json={
        "tetelek": _tetelek(k), "netto_osszeg": 120000,
        "projekt_szoveg": "2026. szeptemberi forgatások (3 nap)", "email_targy": "HYPE – szeptemberi szerződés",
    })
    assert r.status_code == 200 and r.json()["projekt_szoveg"] == "2026. szeptemberi forgatások (3 nap)"
    draft = c.get(f"{SZ}/{ps[0].id}").json()["pending"][0]["draft"]
    assert draft["email_targy"] == "HYPE – szeptemberi szerződés"

    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/generate-and-send", json={})
    assert r.status_code == 200, r.text
    assert kint["doc"][-1]["mezok"]["projektnev"] == "2026. szeptemberi forgatások (3 nap)"
    assert kint["level"][-1]["subject"] == "HYPE – szeptemberi szerződés"
    assert _szerzodesek(k)[0].kikuldott_targy == "HYPE – szeptemberi szerződés"

    # Üres szöveggel vissza a szokásosra.
    k["db"].query(Contract).update({"szerzodes_allapota": "Készítés alatt"})
    c.post(f"{SZ}/{ps[0].id}/{kulcs}/save", json={"projekt_szoveg": "", "email_targy": "  "})
    assert _szerzodesek(k)[0].projekt_szoveg is None and _szerzodesek(k)[0].email_targy is None


def test_tig_osszevonas_elonezet_es_egyedi_szoveg(k):
    c, ps, kulcs, kint = k["c"], k["ps"], k["kulcs"], k["kint"]
    r = c.post(f"{SZ}/{ps[0].id}/{kulcs}/generate-and-send", json={"tetelek": _tetelek(k), "netto_osszeg": 120000})
    assert r.status_code == 200, r.text

    # Félkész TIG a 3. forgatáson - az összevont TIG átveszi.
    r = c.post(f"{TIG}/{ps[2].id}/{kulcs}/save", json={"tetelek": _tetelek(k, [ps[2]]), "netto_osszeg": 40000})
    assert r.status_code == 200, r.text

    adat = {"tetelek": _tetelek(k), "netto_osszeg": 120000, "projekt_szoveg": "Szeptemberi forgatások",
            "email_targy": "Szeptemberi TIG"}
    v = c.post(f"{TIG}/{ps[0].id}/{kulcs}/elonezet", json=adat).json()
    assert v["targy"] == "Szeptemberi TIG" and base64.b64decode(v["pdf_base64"]) == b"%PDF-elonezet"
    assert kint["elonezet"][-1]["mezok"]["projkod"] == "Szeptemberi forgatások"
    assert kint["level"] == [kint["level"][0]]  # csak a szerződés ment ki eddig

    r = c.post(f"{TIG}/{ps[0].id}/{kulcs}/generate-and-send", json=adat)
    assert r.status_code == 200, r.text
    assert kint["level"][-1]["subject"] == "Szeptemberi TIG"
    assert kint["doc"][-1]["mezok"]["projkod"] == "Szeptemberi forgatások"
    tigek = k["db"].query(PerformanceCertificate).filter(PerformanceCertificate.employee_id == k["kulsos"].id).all()
    assert len(tigek) == 1 and {t.project_id for t in tigek[0].tetelek} == {p.id for p in ps}

    # Az adatlapon mindhárom forgatásnál ott a TIG és a szerződés, a pénz egyszer.
    munkak = c.get(f"/api/v1/crew/{k['kulsos'].id}/munkak").json()
    assert len(munkak["projektek"]) == 3
    for s in munkak["projektek"]:
        cimkek = {d["cimke"] for d in s["dokumentumok"]}
        assert {"Szerződés", "TIG"} <= cimkek
    assert munkak["osszes_netto"] == 120000
