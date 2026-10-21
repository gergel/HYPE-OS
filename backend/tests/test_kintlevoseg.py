"""Projekt-kintlévőségek (Pénzügyek): MINDEN ki nem fizetett projektkód bekerül
- számlával vagy anélkül -, csak a kimondottan rendezett marad ki.

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError


@pytest.fixture()
def db():
    from app.core.database import SessionLocal

    try:
        sess = SessionLocal()
        sess.execute(select(1))
    except OperationalError:
        pytest.skip("Postgres nem elérhető — integrációs teszt kihagyva.")
    try:
        yield sess
    finally:
        sess.rollback()
        sess.close()


def _kod(db, kod, **mezok):
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod=kod, **mezok)
    db.add(pc)
    db.flush()
    return pc


def _szamla(db, pc, *, hatarido=None, kifizetve=None, netto=None):
    from app.models.document_attachment import DocumentAttachment

    db.add(DocumentAttachment(entity_type="projectCode", entity_id=pc.id, kategoria="szamla",
                              filename=f"szamla-{pc.id}.pdf", storage_key=f"teszt/{pc.id}", url=f"https://x/{pc.id}",
                              fizetesi_hatarido=hatarido, kifizetve_datuma=kifizetve, netto=netto))
    db.flush()


def _sorok(db):
    from app.services.kintlevoseg import projekt_kintlevosegek

    db.expire_all()
    return {s["projektkod"]: s for s in projekt_kintlevosegek(db) if s["projektkod"].startswith("KINTL-")}


def test_szamlazando_es_kiallitott_de_nem_fizetett(db):
    ma = date.today()
    szamlazando = _kod(db, "KINTL-SZAMLAZANDO", netto_osszeg=500000, datum=ma - timedelta(days=20))
    _kod(db, "KINTL-OSSZEG-NELKUL", datum=ma - timedelta(days=5))
    kint = _kod(db, "KINTL-KINT", netto_osszeg=300000)
    _szamla(db, kint, hatarido=ma - timedelta(days=3), netto=300000)
    fizetve = _kod(db, "KINTL-FIZETVE", netto_osszeg=100000)
    _szamla(db, fizetve, hatarido=ma - timedelta(days=10), kifizetve=ma - timedelta(days=12))
    jovo = _kod(db, "KINTL-JOVO", netto_osszeg=200000, datum=ma + timedelta(days=30))

    s = _sorok(db)
    assert s["KINTL-SZAMLAZANDO"]["allapot"] == "szamlazando"
    assert s["KINTL-SZAMLAZANDO"]["kintlevo_osszeg"] == 500000
    # Összeg nélkül is bekerül - az is teendő.
    assert s["KINTL-OSSZEG-NELKUL"]["allapot"] == "szamlazando"
    assert s["KINTL-OSSZEG-NELKUL"]["kintlevo_osszeg"] is None
    k = s["KINTL-KINT"]
    assert k["allapot"] == "szamla_kint" and k["lejart"] and k["hatarido_napok"] == -3
    assert k["szamlak"][0]["netto"] == 300000
    assert "KINTL-FIZETVE" not in s
    assert s["KINTL-JOVO"]["esemeny_jovobeli"] is True
    assert szamlazando.id and jovo.id


def test_csak_a_kimondottan_rendezett_marad_ki(db):
    _kod(db, "KINTL-TRANZ-NELKUL", netto_osszeg=1000, szamla_kihagyva=True, szamla_kihagyas_oka="beszámítva",
         tranzakcio_nelkul_lezarva=True)
    _kod(db, "KINTL-ELMARADT", netto_osszeg=1000, esemeny_allapota="Elmaradt")
    _kod(db, "KINTL-NULLA-INDOKKAL", netto_osszeg=0, vallalasi_ar_magyarazat="Beszámítva a fizetésébe")
    _kod(db, "KINTL-NOTION-KIFIZETVE", netto_osszeg=1000, szamla_statusza="Kifizetve")
    _kod(db, "KINTL-SZAMLA-NELKUL", netto_osszeg=80000, szamla_kihagyva=True, szamla_kihagyas_oka="Készpénzben fizet")

    s = _sorok(db)
    for kod in ("KINTL-TRANZ-NELKUL", "KINTL-ELMARADT", "KINTL-NULLA-INDOKKAL", "KINTL-NOTION-KIFIZETVE"):
        assert kod not in s, kod
    # Számla nem lesz, de a pénz sincs lezárva → nem tűnhet el csendben.
    sn = s["KINTL-SZAMLA-NELKUL"]
    assert sn["allapot"] == "szamla_nelkul" and sn["megjegyzes"] == "Készpénzben fizet"


def test_hype24_kivett_es_osztott_fizetes(db):
    from app.models.finance import Revenue

    _kod(db, "HYPE24-KINTL-TESZT", netto_osszeg=1000)
    osztott = _kod(db, "KINTL-OSZTOTT")
    ma = date.today()
    db.add_all([
        Revenue(project_code_id=osztott.id, netto=400000, fizetes_datuma=ma - timedelta(days=40)),
        Revenue(project_code_id=osztott.id, netto=600000, szamla_kiallitva_datuma=ma - timedelta(days=10)),
    ])
    db.flush()

    from app.services.kintlevoseg import projekt_kintlevosegek

    db.expire_all()
    kodok = {s["projektkod"] for s in projekt_kintlevosegek(db)}
    assert "HYPE24-KINTL-TESZT" not in kodok
    o = _sorok(db)["KINTL-OSZTOTT"]
    assert o["allapot"] == "szamla_kint" and o["kintlevo_osszeg"] == 600000
    assert o["hatarido_hianyzik"] is True


def test_osszesito_es_api(db):
    from app.services.kintlevoseg import osszesito

    sorok = [
        {"allapot": "szamlazando", "kintlevo_osszeg": 100.0, "lejart": False},
        {"allapot": "szamlazando", "kintlevo_osszeg": None, "lejart": False},
        {"allapot": "szamla_kint", "kintlevo_osszeg": 50.0, "lejart": True},
    ]
    o = osszesito(sorok)
    assert o["szamlazando_db"] == 2 and o["szamlazando_osszeg"] == 100
    assert o["szamla_kint_db"] == 1 and o["lejart_osszeg"] == 50 and o["osszeg_nelkul_db"] == 1

    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    r = TestClient(app).get("/api/v1/finance/summary", headers={"Authorization": f"Bearer {create_access_token('2', 'admin')}"})
    assert r.status_code == 200
    d = r.json()
    assert "szamlazando_db" in d and d["kintlevo_projektek_szama"] == len(d["kintlevo_projektek"])
