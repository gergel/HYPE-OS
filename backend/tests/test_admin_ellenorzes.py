"""Adminisztráció ellenőrzése (a felhasználó kérése, 2026-10): tevékenységnapló
(ki, mikor, mit), kivételek tulajdonosi jelöléssel, lejárt hiányok, heti
összesítő, és Lara figyelése - ami CSAK a tulajdonosnak jelez.

A levélküldés le van cserélve. Tranzakcióban fut a helyi adatbázison, és a
végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.admin_ellenorzes import ALAP_KEZDET, AdminTevekenyseg, LaraFigyelesJelzes
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
    # A teszt-forgatások a valódi kezdőnap (2026.10.05.) előttiek is lehetnek -
    # itt 60 nappal korábbról nézzük; a kezdőnap szűrését külön teszt nézi.
    from app.services import admin_ellenorzes

    admin_ellenorzes.beallitas(db).figyeles_kezdete = date.today() - timedelta(days=60)
    db.flush()
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


def test_csak_a_kezdonaptol_nez(k):
    """A felhasználó kérése: az egész rendszer csak a kezdőnaptól (alapból
    2026.10.05., a kolléga első napja) nézze a dolgokat."""
    c, db, p, kulcs = k["c"], k["db"], k["lezajlott"], f"e{k['kulsos'].id}"
    c.post(f"{SZ}/{p.id}/{kulcs}/skip", json={"kihagyas_oka": "A partnercég számlázza, velünk nincs szerződése."})
    _mint(k, "tulaj")
    assert c.get(f"{AE}/beallitasok").json()["figyeles_kezdete"] == (date.today() - timedelta(days=60)).isoformat()
    assert any(h["project_id"] == p.id for h in c.get(f"{AE}/lejart").json())
    assert c.get(f"{AE}/naplo").json() and c.get(f"{AE}/kivetelek").json()

    # A kezdőnap a 20 napja lezajlott forgatás utánra kerül: se lejárt hiány,
    # se a korábbi napló/kivétel nem látszik, a heti összesítő is a kezdőnaptól indul.
    holnap = date.today() + timedelta(days=1)
    r = c.put(f"{AE}/beallitasok", json={"figyeles_kezdete": holnap.isoformat()})
    assert r.status_code == 200 and r.json()["figyeles_kezdete"] == holnap.isoformat()
    assert not [h for h in c.get(f"{AE}/lejart").json() if h["project_id"] == p.id]
    assert c.get(f"{AE}/naplo").json() == []
    assert not [s for s in c.get(f"{AE}/kivetelek").json() if s["projekt"].startswith("Lezajlott")]
    o = c.get(f"{AE}/osszesito").json()
    assert len(o["hetek"]) == 1 and o["hetek"][0]["osszes"] == 0
    assert o["szamok"]["lejart_hiany"] == 0

    # Üresen hagyva a 2026.10.05. az alap.
    from app.services import admin_ellenorzes

    admin_ellenorzes.beallitas(db).figyeles_kezdete = None
    assert admin_ellenorzes.kezdet(admin_ellenorzes.beallitas(db)) == ALAP_KEZDET == date(2026, 10, 5)


def test_heti_attekintes_hetfo_reggel_egyszer(k):
    """Lara hetente (hétfő 7:00, magyar idő) nézi át a kollégát, és összefoglalót
    ír az előző hétről - a hét közbeni óránkénti ránézés nem csinál semmit."""
    from app.services import lara_figyeles

    c, db, p, kulcs = k["c"], k["db"], k["lezajlott"], f"e{k['kulsos'].id}"
    c.post(f"{SZ}/{p.id}/{kulcs}/skip", json={"kihagyas_oka": "nem kell"})
    # A naplósort a múlt hétre tesszük (a heti összefoglaló az előző hetet nézi).
    hetfo = date.today() - timedelta(days=date.today().weekday())
    sor = db.query(AdminTevekenyseg).one()
    sor.letrejott_at = datetime.combine(hetfo - timedelta(days=5), datetime.min.time(), tzinfo=timezone.utc).replace(hour=10)
    db.flush()
    # Ez a hétfő 8:00 magyar idő (UTC-ben 6:00 vagy 7:00 - mindkettő 7 óra után).
    hetfo_reggel = datetime.combine(hetfo, datetime.min.time(), tzinfo=timezone.utc).replace(hour=7)

    # Kikapcsolva semmi.
    assert lara_figyeles.heti_attekintes(db, most=hetfo_reggel)["allapot"] == "kikapcsolva"
    _mint(k, "tulaj")
    c.put(f"{AE}/beallitasok", json={"figyelt_employee_id": k["kollega"].id, "lara_figyeles": True})
    assert c.get(f"{AE}/beallitasok").json()["heti_attekintes_at"] is None

    e = lara_figyeles.heti_attekintes(db, most=hetfo_reggel)
    assert e["allapot"] == "lefutott" and e["heti"] is True
    heti = db.query(LaraFigyelesJelzes).filter_by(szabaly="heti_osszegzes").one()
    assert heti.cim.startswith("Heti áttekintés – Adminos Kolléga (demó)")
    assert heti.szint == "figyelem"  # semmitmondó indok + 20 napos késés
    assert "Kihagyás / kivétel: 1" in heti.leiras and heti.adat["osszes"] == 1
    assert {"semmitmondo_indok", "nagy_keses"} <= {j.szabaly for j in db.query(LaraFigyelesJelzes).all()}

    # Ugyanazon a héten (pl. szerdán) már nem esedékes, a következő hétfőn igen.
    assert lara_figyeles.heti_attekintes(db, most=hetfo_reggel + timedelta(days=2))["allapot"] == "nem_esedekes"
    # Jövő hétfő 3:00 UTC (magyar idő szerint még 7 óra előtt) - még nem.
    assert not lara_figyeles.heti_esedekes(lara_figyeles.admin_ellenorzes.beallitas(db),
                                           hetfo_reggel + timedelta(days=6, hours=20))
    assert lara_figyeles.heti_attekintes(db, most=hetfo_reggel + timedelta(days=7))["allapot"] == "lefutott"
    # Hétfő hajnalban (7 előtt) még a múlt heti számít.
    hajnal = datetime.combine(hetfo + timedelta(days=14), datetime.min.time(), tzinfo=timezone.utc).replace(hour=3)
    assert lara_figyeles.heti_idopont(hajnal).date() == hetfo + timedelta(days=7)
    assert lara_figyeles.kovetkezo_heti(hetfo_reggel).date() == hetfo + timedelta(days=7)

    # A kézi gomb bármikor lefut (de ugyanarról a hétről nem ír még egy összefoglalót).
    db_elotte = db.query(LaraFigyelesJelzes).filter_by(szabaly="heti_osszegzes").count()
    assert c.post(f"{AE}/lara/futtatas").json()["allapot"] == "lefutott"
    assert db.query(LaraFigyelesJelzes).filter_by(szabaly="heti_osszegzes").count() <= db_elotte + 1
