"""Alvállalkozói szerződés aláírás-emlékeztető (a felhasználó kérése, 2026-10):
ha a kiküldött szerződés 7 nap alatt sem jött vissza aláírva, a felület
felajánlja a "kérjük, küldd vissza aláírva" válasz-levelet ugyanarra a címre,
ugyanabba a szálba - és csak gombnyomásra küldi ki.

A levélküldés le van cserélve (semmi nem megy ki). Tranzakcióban fut a helyi
adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.contract import Contract, ContractType
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.project import Project
from app.services import szerzodes_emlekezteto as em

MOST = datetime.now(timezone.utc)


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
def admin(db):
    e = Employee(full_name="Emlékeztető Admin (demó)", tipus=EmployeeType.BELSOS,
                 email="emlek-admin-demo@example.test", role=SystemRole.ADMIN, is_active=True)
    db.add(e)
    db.flush()
    return e


@pytest.fixture
def szerzodes(db):
    kulsos = Employee(full_name="Külsős Operatőr (demó)", tipus=EmployeeType.KULSOS,
                      email="kulsos-demo@example.test", is_active=True)
    projekt = Project(nev="Szerződéses forgatás (demó)", forgatas_datuma=date(2026, 9, 1))
    db.add_all([kulsos, projekt])
    db.flush()
    c = Contract(tipus=ContractType.ALVALLALKOZOI, keretszerzodes=False, employee_id=kulsos.id,
                 project_id=projekt.id, szerzodes_allapota="Kiküldve", netto_osszeg=50_000,
                 keltezes=date(2026, 9, 1))
    em.kikuldes_rogzitese(c, cimzett="kulsos-demo@example.test", targy="2026-09-01_Forgatás_Külsős_szerződés",
                          kuldes_eredmenye=("thr-1", "gm-1", "<rfc-1@mail.gmail.com>"))
    c.kikuldve_at = MOST - timedelta(days=8)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def kuldott(monkeypatch):
    levelek: list[dict] = []

    def hamis_kuldes(to_list, subject, html, **kw):
        levelek.append({"to": to_list, "subject": subject, "html": html, **kw})
        return ("thr-1", "gm-2", "<rfc-2@mail.gmail.com>")

    monkeypatch.setattr("app.api.routes.subcontractor_contracts.send_message", hamis_kuldes)
    return levelek


def _kliens(db, admin):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    return TestClient(app), app


def test_kikuldes_rogzitese_a_szalat_es_a_cimet_menti(szerzodes):
    assert szerzodes.gmail_thread_id == "thr-1"
    assert szerzodes.gmail_rfc_message_id == "<rfc-1@mail.gmail.com>"
    assert szerzodes.kikuldott_cim == "kulsos-demo@example.test"
    assert szerzodes.emlekezteto_db == 0


def test_esedekesseg(szerzodes):
    assert em.esedekes(szerzodes, MOST) and em.napja(szerzodes, MOST) == 8
    # 7 napon belül még nem.
    szerzodes.kikuldve_at = MOST - timedelta(days=6)
    assert not em.esedekes(szerzodes, MOST)
    szerzodes.kikuldve_at = MOST - timedelta(days=8)
    # Aláírva (feltöltve vagy kézzel jelölve) már nem vár.
    szerzodes.alairt_file_url = "https://example.test/alairt.pdf"
    assert not em.esedekes(szerzodes, MOST) and em.napja(szerzodes, MOST) is None
    szerzodes.alairt_file_url = None
    szerzodes.alairva = True
    assert not em.esedekes(szerzodes, MOST)
    szerzodes.alairva = False
    # Kihagyott szerződésre nincs mit emlékeztetni.
    szerzodes.szerzodes_allapota = "Kihagyva"
    assert not em.esedekes(szerzodes, MOST)
    szerzodes.szerzodes_allapota = "Kiküldve"
    # Az előző emlékeztető óta is 7 napnak kell eltelnie.
    szerzodes.emlekezteto_kuldve_at = MOST - timedelta(days=3)
    assert not em.esedekes(szerzodes, MOST)
    szerzodes.emlekezteto_kuldve_at = MOST - timedelta(days=7, hours=1)
    assert em.esedekes(szerzodes, MOST)


def test_regi_szerzodes_csak_ha_a_rendszer_generalta(szerzodes):
    szerzodes.kikuldve_at = None
    szerzodes.keltezes = (MOST - timedelta(days=10)).date()
    # Feltöltött saját szerződés (nem e-mailben ment ki): nincs emlékeztető.
    szerzodes.szerzodes_file_url = "https://tarhely.example.test/szerzodes.pdf"
    assert not em.esedekes(szerzodes, MOST)
    szerzodes.szerzodes_file_url = "https://docs.google.com/document/d/abc/edit"
    assert em.esedekes(szerzodes, MOST)


def test_emlekezteto_ugyanabba_a_szalba_megy_es_nem_kuldheto_ketszer(db, admin, szerzodes, kuldott):
    c, app = _kliens(db, admin)
    try:
        lista = c.get(f"/api/v1/alvallalkozoi-szerzodesek/{szerzodes.project_id}/all")
        assert lista.status_code == 200, lista.text
        sor = next(s for s in lista.json() if s["contract_id"] == szerzodes.id)
        assert sor["emlekezteto_esedekes"] is True and sor["kikuldve_napja"] == 8
        assert sor["emlekezteto_cimzett"] == "kulsos-demo@example.test"

        r = c.post(f"/api/v1/alvallalkozoi-szerzodesek/szerzodes/{szerzodes.id}/emlekezteto")
        assert r.status_code == 200, r.text
        assert r.json()["cimzett"] == "kulsos-demo@example.test" and r.json()["emlekezteto_db"] == 1
        assert len(kuldott) == 1
        level = kuldott[0]
        assert level["to"] == ["kulsos-demo@example.test"]
        assert level["subject"] == "Re: 2026-09-01_Forgatás_Külsős_szerződés"
        assert level["thread_id"] == "thr-1" and level["in_reply_to"] == "<rfc-1@mail.gmail.com>"
        assert "aláírva" in level["html"]

        # Dupla kattintás / frissítetlen oldal: másodszor már nem megy ki.
        r = c.post(f"/api/v1/alvallalkozoi-szerzodesek/szerzodes/{szerzodes.id}/emlekezteto")
        assert r.status_code == 409
        assert len(kuldott) == 1
        sor = next(s for s in c.get(f"/api/v1/alvallalkozoi-szerzodesek/{szerzodes.project_id}/all").json()
                   if s["contract_id"] == szerzodes.id)
        assert sor["emlekezteto_esedekes"] is False and sor["emlekezteto_db"] == 1
    finally:
        app.dependency_overrides.clear()


def test_alairt_szerzodesre_nem_megy_emlekezteto(db, admin, szerzodes, kuldott):
    szerzodes.alairva = True
    db.flush()
    c, app = _kliens(db, admin)
    try:
        r = c.post(f"/api/v1/alvallalkozoi-szerzodesek/szerzodes/{szerzodes.id}/emlekezteto")
        assert r.status_code == 409 and not kuldott
    finally:
        app.dependency_overrides.clear()


def test_regi_szerzodesnel_uj_level_az_eredeti_targgyal(db, admin, szerzodes, kuldott):
    szerzodes.kikuldve_at = None
    szerzodes.kikuldott_targy = None
    szerzodes.gmail_thread_id = None
    szerzodes.gmail_rfc_message_id = None
    szerzodes.kikuldott_cim = None
    szerzodes.keltezes = (MOST - timedelta(days=30)).date()
    szerzodes.szerzodes_file_url = "https://docs.google.com/document/d/abc/edit"
    db.flush()
    c, app = _kliens(db, admin)
    try:
        r = c.post(f"/api/v1/alvallalkozoi-szerzodesek/szerzodes/{szerzodes.id}/emlekezteto")
        assert r.status_code == 200, r.text
        level = kuldott[0]
        # A címzett a külsős saját címe, a tárgy az eredeti szerződés-levélé.
        assert level["to"] == ["kulsos-demo@example.test"]
        assert level["subject"] == "Re: 2026-09-01_Szerződéses forgatás (demó)_Külsős Operatőr (demó)_szerződés"
        assert level["thread_id"] is None and level["in_reply_to"] is None
    finally:
        app.dependency_overrides.clear()


def test_generalas_es_kuldes_rogziti_a_szalat(db, admin, kuldott, monkeypatch):
    """A kiküldés (projektkódos ág) elmenti, kinek és melyik szálban ment ki -
    erre válaszol később az emlékeztető. A számlázó fél ellenőrzését itt
    kiváltjuk; a Google Docs-generálás nincs beállítva, így PDF nélkül megy."""
    from app.api.routes import subcontractor_contracts as sc
    from app.core.config import settings
    from app.models.project_code import ProjectCode
    from app.services.szamlazo import SzamlazoCsoport, SzamlazoFel

    kulsos = Employee(full_name="Külsős Vágó (demó)", tipus=EmployeeType.KULSOS,
                      email="vago-demo@example.test", is_active=True)
    pk = ProjectCode(projektkod="EMLEK-DEMO-1")
    db.add_all([kulsos, pk])
    db.flush()
    monkeypatch.setattr(settings, "gdoc_alvallalkozoi_szerzodes_template_id", "")
    monkeypatch.setattr(sc, "_validate_szamlazo_projektkodon",
                        lambda _db, _pk, _k: SzamlazoCsoport(fel=SzamlazoFel(employee=kulsos), tagok=[kulsos]))
    c, app = _kliens(db, admin)
    try:
        r = c.post(f"/api/v1/alvallalkozoi-szerzodesek/projektkodok/{pk.id}/e{kulsos.id}/generate-and-send",
                   json={"netto_osszeg": 40_000})
        assert r.status_code == 200, r.text
        szerz = db.get(Contract, r.json()["id"])
        assert szerz.szerzodes_allapota == "Kiküldve"
        assert szerz.kikuldott_cim == "vago-demo@example.test"
        assert szerz.kikuldott_targy == "EMLEK-DEMO-1_Külsős Vágó (demó)_szerződés"
        assert szerz.gmail_thread_id == "thr-1" and szerz.gmail_rfc_message_id == "<rfc-2@mail.gmail.com>"
        assert szerz.kikuldve_at is not None and not em.esedekes(szerz)
    finally:
        app.dependency_overrides.clear()
