"""Adminisztráció ellenőrzése (a felhasználó kérése, 2026-10): tevékenységnapló
(ki, mikor, mit), kivételek tulajdonosi jelöléssel, lejárt hiányok, heti
összesítő, és Lara figyelése - ami CSAK a tulajdonosnak jelez.

A levélküldés le van cserélve. Tranzakcióban fut a helyi adatbázison, és a
végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.admin_ellenorzes import AdminTevekenyseg, LaraFigyelesJelzes
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.project import Project
from app.models.task import Task

SZ = "/api/v1/alvallalkozoi-szerzodesek"
AE = "/api/v1/admin-ellenorzes"


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

    tulaj = Employee(full_name="Tulajdonos (demó)", tipus=EmployeeType.BELSOS, email="tulaj-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    kollega = Employee(full_name="Adminos Kolléga (demó)", tipus=EmployeeType.BELSOS, email="adminos-demo@example.test",
                       role=SystemRole.ADMINISZTRACIO, is_active=True)
    masik_admin = Employee(full_name="Másik Admin (demó)", tipus=EmployeeType.BELSOS, email="masik-demo@example.test",
                           role=SystemRole.ADMIN, is_active=True)
    kulsos = Employee(full_name="Külsős Hangos (demó)", tipus=EmployeeType.KULSOS, email="hangos-demo@example.test",
                      is_active=True)
    lezajlott = Project(nev="Lezajlott forgatás (demó)", forgatas_datuma=date.today() - timedelta(days=20))
    friss = Project(nev="Friss forgatás (demó)", forgatas_datuma=date.today() - timedelta(days=1))
    db.add_all([tulaj, kollega, masik_admin, kulsos, lezajlott, friss])
    db.flush()
    lezajlott.crew.append(kulsos)
    friss.crew.append(kulsos)
    db.flush()
    monkeypatch.setattr(settings, "vedett_admin_emailek", "tulaj-demo@example.test")
    monkeypatch.setattr("app.api.routes.subcontractor_contracts.send_message", lambda *a, **kw: ("t", "g", "<r>"))
    ki = {"u": kollega}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: ki["u"]
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "db": db, "ki": ki, "tulaj": tulaj, "kollega": kollega, "masik": masik_admin,
               "kulsos": kulsos, "lezajlott": lezajlott, "friss": friss}
    finally:
        app.dependency_overrides.clear()


def _mint(k, ki):
    k["ki"]["u"] = k[ki]


def test_naplo_ki_mikor_mit_es_csak_a_sikeres_irast(k):
    c, p, kulcs = k["c"], k["lezajlott"], f"e{k['kulsos'].id}"
    # Előnézet és olvasás nem kerül a naplóba, a hibás kérés sem.
    c.post(f"{SZ}/{p.id}/{kulcs}/elonezet?pdf=false", json={})
    c.get(f"{SZ}/{p.id}")
    assert c.post(f"{SZ}/{p.id}/{kulcs}/generate-and-send", json={}).status_code == 400  # nincs összeg
    assert k["db"].query(AdminTevekenyseg).count() == 0

    r = c.post(f"{SZ}/{p.id}/{kulcs}/skip", json={"kihagyas_oka": "nem kell"})
    assert r.status_code == 200, r.text
    sorok = k["db"].query(AdminTevekenyseg).all()
    assert len(sorok) == 1
    s = sorok[0]
    assert s.employee_id == k["kollega"].id and s.muvelet == "kihagyas" and s.targy == "szerzodes"
    assert s.leiras == "Alvállalkozói szerződés: KIHAGYVA"
    assert s.project_id == p.id and s.adat["kihagyas_oka"] == "nem kell"


def test_csak_a_tulajdonos_latja_a_figyelt_kollega_soha(k):
    c = k["c"]
    _mint(k, "masik")
    assert c.get(f"{AE}/osszesito").status_code == 403
    assert c.get(f"{AE}/hozzaferes").json() == {"lathatja": False}
    _mint(k, "tulaj")
    assert c.get(f"{AE}/hozzaferes").json() == {"lathatja": True}
    r = c.put(f"{AE}/beallitasok", json={"figyelt_employee_id": k["kollega"].id, "lara_figyeles": True,
                                          "hataridok": {"tig": 5}})
    assert r.status_code == 200, r.text
    assert r.json()["figyelt_nev"] == "Adminos Kolléga (demó)" and r.json()["hataridok"]["tig"] == 5
    # A figyelt kolléga akkor sem látja, ha tulajdonosi (védett) címe lenne.
    k["kollega"].email = "tulaj-demo@example.test"
    _mint(k, "kollega")
    assert c.get(f"{AE}/lara/jelzesek").status_code == 403


def test_kivetelek_ki_mikor_es_tulajdonosi_dontes(k):
    c, p, kulcs = k["c"], k["lezajlott"], f"e{k['kulsos'].id}"
    c.post(f"{SZ}/{p.id}/{kulcs}/skip", json={"kihagyas_oka": "A partnercég számlázza, velünk nincs szerződése."})
    _mint(k, "tulaj")
    c.put(f"{AE}/beallitasok", json={"figyelt_employee_id": k["kollega"].id})
    lista = c.get(f"{AE}/kivetelek").json()
    sor = next(s for s in lista if s["tipus"] == "Szerződés kihagyva" and s["projekt"].startswith("Lezajlott"))
    assert sor["ki"] == "Adminos Kolléga (demó)" and sor["mikor"] is not None
    assert sor["indok"].startswith("A partnercég") and sor["dontes"] is None
    assert sor["link"] == f"/utokovetes/{p.id}"

    r = c.post(f"{AE}/kivetelek/jeloles", json={"kulcs": sor["kulcs"], "dontes": "visszadobva",
                                                "megjegyzes": "Kérlek nézd meg, van-e mégis szerződés.",
                                                "feladat": True, "cim": sor["tipus"], "link": sor["link"]})
    assert r.status_code == 200, r.text
    feladat = k["db"].get(Task, r.json()["task_id"])
    assert [e.id for e in feladat.felelosok] == [k["kollega"].id]
    assert "nézd át újra" in feladat.feladat
    sor = next(s for s in c.get(f"{AE}/kivetelek").json() if s["kulcs"] == sor["kulcs"])
    assert sor["dontes"] == "visszadobva"
    assert all(s["kulcs"] != sor["kulcs"] for s in c.get(f"{AE}/kivetelek?csak_nyitott=true").json())


def test_lejart_hianyok_es_heti_osszesito(k):
    c = k["c"]
    _mint(k, "tulaj")
    lejart = c.get(f"{AE}/lejart").json()
    sajat = [h for h in lejart if h["project_id"] == k["lezajlott"].id]
    assert {h["tipus"] for h in sajat} >= {"szerzodes", "tig"}
    szerzodes = next(h for h in sajat if h["tipus"] == "szerzodes")
    assert szerzodes["eltelt_nap"] == 20 and szerzodes["keses_nap"] == 17
    # A tegnapi forgatás még nem késik.
    assert not [h for h in lejart if h["project_id"] == k["friss"].id]

    _mint(k, "kollega")
    c.post(f"{SZ}/{k['lezajlott'].id}/e{k['kulsos'].id}/generate-and-send", json={"netto_osszeg": 50000})
    _mint(k, "tulaj")
    c.put(f"{AE}/beallitasok", json={"figyelt_employee_id": k["kollega"].id})
    o = c.get(f"{AE}/osszesito").json()
    assert o["hetek"][0]["kikuldes"] >= 1 and o["hetek"][0]["figyelt"] >= 1
    assert set(o["szamok"]) == {"atnezetlen_kivetel", "lejart_hiany", "nyitott_jelzes"}


def test_lara_figyeles_csak_bekapcsolva_es_csak_egyszer_jelez(k, monkeypatch):
    from app.services import lara_figyeles

    c, db, p, kulcs = k["c"], k["db"], k["lezajlott"], f"e{k['kulsos'].id}"
    c.post(f"{SZ}/{p.id}/{kulcs}/skip", json={"kihagyas_oka": "nem kell"})
    c.delete(f"{SZ}/{p.id}/{kulcs}")

    # Alapból KI: az időzített kör nem csinál semmit.
    assert lara_figyeles.futtat(db)["allapot"] == "kikapcsolva"
    assert db.query(LaraFigyelesJelzes).count() == 0

    _mint(k, "tulaj")
    c.put(f"{AE}/beallitasok", json={"figyelt_employee_id": k["kollega"].id, "lara_figyeles": True})
    e = lara_figyeles.futtat(db)
    assert e["allapot"] == "lefutott" and e["uj_jelzes"] >= 2
    szabalyok = {j.szabaly for j in db.query(LaraFigyelesJelzes).all()}
    assert {"semmitmondo_indok", "torles"} <= szabalyok
    # A 20 napja lezajlott forgatás szerződése 17 napja késik -> nagy késés.
    assert "nagy_keses" in szabalyok
    # Másodszor ugyanarról nem szól.
    assert lara_figyeles.futtat(db)["uj_jelzes"] == 0

    jelzesek = c.get(f"{AE}/lara/jelzesek").json()
    assert jelzesek and all(j["lezarva_at"] is None for j in jelzesek)
    assert c.post(f"{AE}/lara/jelzesek/{jelzesek[0]['id']}/lezaras").status_code == 200
    assert len(c.get(f"{AE}/lara/jelzesek").json()) == len(jelzesek) - 1

    # Vészleállításnál Lara nem figyel.
    from app.admin_agent.settings_service import get_settings

    get_settings(db).kill_switch = True
    assert lara_figyeles.futtat(db)["allapot"] == "veszleallitas"
