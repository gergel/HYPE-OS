"""Gyártás-TV — heti forgatások (stáb), ki mit vág épp, kiküldhető, gyártásra
vár. Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.deliverable import Deliverable
from app.models.deliverable_status import DeliverableStatusConfig
from app.models.employee import Employee, EmployeeType
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.services.gyartas_tv import auto_csoport, tv_adatok


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


# Egy rögzített szerda: a hét hétfőtől vasárnapig tart.
SZERDA = date(2031, 3, 12)


def _ember(db, nev: str) -> Employee:
    e = Employee(full_name=nev, tipus=EmployeeType.BELSOS, is_active=True, szin="#3366ff")
    db.add(e)
    db.flush()
    return e


def test_allapot_nev_szerinti_oszlop():
    assert auto_csoport("Aktuális") == "vagas"
    assert auto_csoport("Javítás") == "vagas"
    assert auto_csoport("Beérkező") == "ellenorzes"
    assert auto_csoport("Ellenőrzésre vár") == "ellenorzes"
    assert auto_csoport("Kiküldhető") == "kikuldheto"
    assert auto_csoport("Kiküldésre vár") == "kikuldheto"
    assert auto_csoport("Kész kiküldve") == "rejtett"
    assert auto_csoport("Gyártásra vár") == "gyartasra_var"
    assert auto_csoport("Kérdés a gyártásnak") == "gyartasra_var"
    assert auto_csoport(None) is None


def test_heti_forgatasok_stabbal_es_ma(db):
    anna, bela = _ember(db, "TV Teszt Anna"), _ember(db, "TV Teszt Béla")
    p1 = Project(nev="TV-teszt forgatás (szerda)", forgatas_datuma=SZERDA, helyszin="Stúdió 1")
    p1.crew = [anna, bela]
    p2 = Project(nev="TV-teszt kétnapos", forgatas_datuma=SZERDA - timedelta(days=3),
                 forgatas_datuma_vege=SZERDA - timedelta(days=1))  # vasárnaptól keddig
    p3 = Project(nev="TV-teszt jövő hét", forgatas_datuma=SZERDA + timedelta(days=7))
    db.add_all([p1, p2, p3])
    db.flush()
    d = tv_adatok(db, ma=SZERDA)
    assert d["het"] == {"tol": "2031-03-10", "ig": "2031-03-16"}
    napok = {n["nev"]: n for n in d["napok"]}
    assert napok["Szerda"]["ma"] and [f["nev"] for f in napok["Szerda"]["forgatasok"]] == ["TV-teszt forgatás (szerda)"]
    assert "TV-teszt kétnapos" in [f["nev"] for f in napok["Hétfő"]["forgatasok"]]
    assert "TV-teszt kétnapos" in [f["nev"] for f in napok["Kedd"]["forgatasok"]]
    assert all("TV-teszt jövő hét" not in [f["nev"] for f in n["forgatasok"]] for n in d["napok"])
    assert {e["nev"] for e in d["ma_forgat"]} >= {"TV Teszt Anna", "TV Teszt Béla"}
    assert napok["Szerda"]["forgatasok"][0]["stab"][0]["szin"] == "#3366ff"


def test_vagasok_oszlopai_felulirassal_es_futo_merovel(db):
    vago = _ember(db, "TV Teszt Vágó")
    db.add(DeliverableStatusConfig(allapot="TV-teszt Megrendelőnél", tv_csoport="gyartasra_var", sorrend=99))
    anyagok = {
        a: Deliverable(projekt_neve=f"TV-teszt {a}", allapot=a, vago_employee_id=vago.id, hatarido=SZERDA + timedelta(days=2))
        for a in ("Aktuális", "Beérkező", "Kiküldhető", "Gyártásra vár", "TV-teszt Megrendelőnél", "Kész kiküldve")
    }
    db.add_all(anyagok.values())
    db.flush()
    db.add(Timesheet(employee_id=vago.id, deliverable_id=anyagok["Aktuális"].id,
                     start_date=datetime.now(timezone.utc) - timedelta(minutes=20)))
    db.flush()
    d = tv_adatok(db, ma=SZERDA)
    v = d["vagasok"]

    def nevek(cs):
        return {x["projekt"] for x in v[cs] if x["projekt"].startswith("TV-teszt")}

    assert nevek("vagas") == {"TV-teszt Aktuális"}
    assert nevek("ellenorzes") == {"TV-teszt Beérkező"}
    assert nevek("kikuldheto") == {"TV-teszt Kiküldhető"}
    assert nevek("gyartasra_var") == {"TV-teszt Gyártásra vár", "TV-teszt TV-teszt Megrendelőnél"}
    assert all(not x["projekt"].endswith("Kész kiküldve") for cs in v.values() for x in cs)
    akt = next(x for x in v["vagas"] if x["projekt"] == "TV-teszt Aktuális")
    assert akt["fut"][0]["nev"] == "TV Teszt Vágó" and akt["emberek"][0]["nev"] == "TV Teszt Vágó"
    assert any(e["nev"] == "TV Teszt Vágó" for e in d["most_vag"])


def test_api_jogosultsaggal(db):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    r = TestClient(app).get("/api/v1/gyartas/tv", headers={"Authorization": f"Bearer {create_access_token('2', 'admin')}"})
    assert r.status_code == 200 and set(r.json()) >= {"napok", "vagasok", "ma_forgat", "most_vag", "osszesito"}
    assert TestClient(app).get("/api/v1/gyartas/tv").status_code == 401
