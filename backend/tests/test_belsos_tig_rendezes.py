"""Belsős TIG visszamenőleges rendezése (a felhasználó kérése, 2026-10): éves
áttekintés (ki mikor mennyit), kézi áthelyezés az elcsúszott hónapból (a
dátumok utána nem tolják vissza), csere, régi hónap összegének javítása,
TIG feltöltése kiküldés helyett, kifizetve jelölés Kiadás sor nélkül.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK. A
tárhely-feltöltés le van cserélve."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.employee_monthly_item import EmployeeMonthlyItem
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate as Tig
from app.services.hu_datum import belsos_tig_honapja

EV = 2025


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
    from app.services import document_storage

    monkeypatch.setattr(document_storage, "upload_bytes", lambda data, key, ct: f"https://tarhely.example.test/{key}")
    monkeypatch.setattr(document_storage, "delete_object", lambda key: None)
    admin = Employee(full_name="Rendező Admin (demó)", tipus=EmployeeType.BELSOS, email="rendezo-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    belsos = Employee(full_name="Rendezendő Belsős (demó)", tipus=EmployeeType.BELSOS, is_active=True)
    db.add_all([admin, belsos])
    db.flush()
    db.add(BelsosIdoszak(employee_id=belsos.id, kezdet=date(EV, 1, 1), veg=date(EV, 12, 31)))
    # Elcsúszott júniusi sor: a teljesítés a ledolgozott hónapban áll (06.01),
    # ezért a dátum szerint májusra mutatna. Júliusban rendes sor tétellel.
    jun = Tig(employee_id=belsos.id, ev=EV, honap=6, allapot="Kiküldve", netto_osszeg=400_000,
              teljesites_datuma=date(EV, 6, 1), fizetesi_hatarido=date(EV, 7, 20))
    jul = Tig(employee_id=belsos.id, ev=EV, honap=7, allapot="Készítés alatt", netto_osszeg=450_000,
              teljesites_datuma=date(EV, 8, 20), fizetesi_hatarido=date(EV, 8, 20))
    db.add_all([jun, jul])
    db.flush()
    db.add(EmployeeMonthlyItem(employee_id=belsos.id, ev=EV, honap=7, tipus="alapber", megnevezes="Alapbér (demó)",
                               osszeg=450_000))
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "e": belsos, "jun": jun, "jul": jul}
    finally:
        app.dependency_overrides.clear()


def _sor(k):
    lista = k["c"].get(f"/api/v1/belsos-tig/rendezes?ev={EV}").json()
    return next(s for s in lista if s["employee_id"] == k["e"].id)


def test_eves_attekintes_ki_mikor_mennyit(k):
    sor = _sor(k)
    assert len(sor["honapok"]) == 12 and sor["osszesen"] == 850_000
    jun = sor["honapok"][5]
    assert jun["netto_osszeg"] == 400_000 and jun["belsos"] is True and jun["kell_tig"] is True
    # A dátumok szerint a teljesítés májusra mutat - ebből látszik az elcsúszás.
    assert jun["datumok_szerint"] == {"teljesítés": f"{EV}. május"}
    assert sor["honapok"][6]["van_tetel"] is True


def test_athelyezes_tetelekkel_es_a_datum_nem_tolja_vissza(db, k):
    c, e = k["c"], k["e"]
    r = c.post(f"/api/v1/belsos-tig/{e.id}/{EV}/7/athelyezes", json={"cel_ev": EV, "cel_honap": 8})
    assert r.status_code == 200, r.text
    db.refresh(k["jul"])
    assert (k["jul"].ev, k["jul"].honap, k["jul"].honap_rogzitve) == (EV, 8, True)
    assert db.scalar(select(EmployeeMonthlyItem.honap).where(EmployeeMonthlyItem.employee_id == e.id)) == 8
    # Egy későbbi mentés a (más hónapra mutató) dátummal sem tolja vissza.
    r = c.post(f"/api/v1/belsos-tig/{e.id}/{EV}/8/save", json={"megjegyzes": "javítva (demó)"})
    assert r.status_code == 200, r.text
    db.refresh(k["jul"])
    assert (k["jul"].ev, k["jul"].honap) == (EV, 8)
    # A megnevezés is a tárolt hónapot követi.
    assert belsos_tig_honapja(EV, 8, date(EV, 8, 20), None, None, rogzitett=True) == (EV, 8)


def test_foglalt_honap_409_cserevel_helyet_cserelnek(db, k):
    c, e = k["c"], k["e"]
    r = c.post(f"/api/v1/belsos-tig/{e.id}/{EV}/6/athelyezes", json={"cel_ev": EV, "cel_honap": 7})
    assert r.status_code == 409
    r = c.post(f"/api/v1/belsos-tig/{e.id}/{EV}/6/athelyezes", json={"cel_ev": EV, "cel_honap": 7, "csere": True})
    assert r.status_code == 200, r.text
    db.refresh(k["jun"])
    db.refresh(k["jul"])
    assert (k["jun"].honap, k["jul"].honap) == (7, 6)
    assert k["jun"].honap_rogzitve and k["jul"].honap_rogzitve
    # A tételek is cseréltek: a júliusi alapbér most júniusban.
    assert db.scalar(select(EmployeeMonthlyItem.honap).where(EmployeeMonthlyItem.employee_id == e.id)) == 6


def test_regi_honap_osszege_javithato_ha_nincs_tetele(db, k):
    c, e = k["c"], k["e"]
    r = c.post(f"/api/v1/belsos-tig/{e.id}/{EV}/6/rendezes-osszeg", json={"netto_osszeg": 410_000})
    assert r.status_code == 200, r.text
    assert r.json()["netto_osszeg"] == 410_000
    assert c.post(f"/api/v1/belsos-tig/{e.id}/{EV}/7/rendezes-osszeg", json={"netto_osszeg": 1}).status_code == 409


def test_tig_feltoltes_szamla_es_kifizetve_kiadas_nelkul(db, k):
    c, e = k["c"], k["e"]
    alap = f"/api/v1/belsos-tig/{e.id}/{EV}/7"
    r = c.post(f"{alap}/tig-fajl", files={"file": ("tig.pdf", b"%PDF demo", "application/pdf")})
    assert r.status_code == 200 and r.json()["allapot"] == "Kiküldve"
    r = c.post(f"{alap}/szamla", files={"file": ("szamla.pdf", b"%PDF demo", "application/pdf")})
    assert r.status_code == 200 and len(r.json()["invoices"]) == 1
    kiadas_elotte = db.query(Expense).count()
    r = c.post(f"{alap}/szamla-kifizetve", json={"kiadasba_kerul": False, "kifizetes_datuma": f"{EV}-08-15"})
    assert r.status_code == 200, r.text
    db.refresh(k["jul"])
    assert k["jul"].szamla_kifizetve and k["jul"].utalas_datuma == date(EV, 8, 15) and k["jul"].expense_id is None
    assert db.query(Expense).count() == kiadas_elotte
    honap = _sor(k)["honapok"][6]
    assert honap["szamla_kifizetve"] and honap["tig_fajl_url"] and len(honap["szamlak"]) == 1
