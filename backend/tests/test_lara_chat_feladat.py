"""Feladat Larának a beszélgetésből: felismerés, rákérdezés, létrehozás csak
megerősítésre, hatáskör. Rollbackes DB-teszt, modell nélkül."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import chat_feladat as cf
from app.models.admin_agent import ActionTrace, AdminTask
from app.models.employee import Employee


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
        from app.admin_agent import llm, nyomozas

        nyomozas.teszt_beszelgetes(None)
        llm.teszt_adapter(None)
        sess.rollback()
        sess.close()


@pytest.fixture()
def admin(db):
    e = db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin.")
    return e


def test_felismeres():
    ma = date(2026, 9, 28)  # hétfő
    assert cf.felismer("Mennyibe került a TTM projekt?") is None
    assert cf.felismer("Kell TIG a Kovács (demó) Kft.-hez?") is None
    j = cf.felismer("Intézd el, hogy a Kovács (demó) Kft. küldjön TIG-et péntekig. Sürgős.")
    assert j["tipus"] == "tig" and j["cim"] == "Intézd el, hogy a Kovács (demó) Kft. küldjön TIG-et péntekig."
    assert cf._hatarido_tipp("péntekig", ma) == "2026-10-02" and cf._hatarido_tipp("holnap", ma) == "2026-09-29"
    j = cf.felismer("Vedd fel feladatnak: szerződés a Fénykép (demó) Stúdiónak 2026-10-05-ig")
    assert j["kifejezett"] and j["tipus"] == "szerzodes" and j["hatarido"] == "2026-10-05"
    assert cf.felismer("Írj egy levelet a könyvelőnek a szeptemberi számlákról")["tipus"] == "email"
    assert "Utalást" in cf.hataskoron_kivul("Utald el a Kovács számláját")
    assert cf.osszevon(cf.felismer("Készíts utalást és fizesd ki"), None, "Készíts utalást és fizesd ki") is None
    assert cf.hataskoron_kivul("Rakd át a diszpót holnapra") is not None


def test_valaszban_rakerdez_letrehozas_csak_megerositesre(db, admin):
    from app.admin_agent import beszelgetes as bz

    b = bz.uj(db, admin)
    _, v = bz.valaszol(db, admin, b, "Írj egy levelet a Kovács (demó) Kft.-nek a hiányzó TIG-ről holnapig.")
    fj = v.adat["feladat_javaslat"]
    assert fj["allapot"] == "javasolt" and fj["tipus"] in ("email", "tig")
    elotte = db.scalar(select(AdminTask.id).order_by(AdminTask.id.desc()))
    assert elotte == db.scalar(select(AdminTask.id).order_by(AdminTask.id.desc()))  # még nincs feladat

    j = cf.letrehoz(db, admin, v.id, {"tipus": "email", "partner": "Kovács (demó) Kft."})
    t = db.get(AdminTask, j["task_id"])
    assert t.tipus == "email" and t.allapot == "new" and t.trust_level == "L0" and t.partner_nev == "Kovács (demó) Kft."
    assert t.forras_referenciak["lara_chat"]["uzenet_id"] == v.id and t.hatarido is not None
    assert db.scalar(select(ActionTrace).where(ActionTrace.task_id == t.id)).muvelet == "feladat_beszelgetesbol"
    # Egy javaslatból egy feladat.
    assert cf.letrehoz(db, admin, v.id, {})["task_id"] == t.id
    uzenetek = bz.uzenetek(db, b)
    assert uzenetek[-1]["adat"]["tipus"] == "feladat_letrehozva" and uzenetek[-1]["adat"]["task_id"] == t.id


def test_kerdesre_nincs_rakerdezes_utalasra_elutasitas(db, admin):
    from app.admin_agent import beszelgetes as bz

    b = bz.uj(db, admin)
    _, v = bz.valaszol(db, admin, b, "Mennyibe kerültek a TTM projektek?")
    assert "feladat_javaslat" not in v.adat
    _, v2 = bz.valaszol(db, admin, b, "Utald el most a Kovács (demó) számláját.")
    assert "feladat_javaslat" not in v2.adat and "Utalást" in v2.adat["feladat_elutasitva"]


def test_kozvetlen_elvetes_es_hibas_adat(db, admin, ):
    from app.admin_agent import beszelgetes as bz

    b = bz.uj(db, admin)
    _, v = cf.kozvetlen(db, admin, b, "Szerződés-tervezet a Csiripelő (demó) Kft.-nek")
    assert v.adat["feladat_javaslat"]["kifejezett"] is True
    with pytest.raises(cf.FeladatHiba):
        cf.letrehoz(db, admin, v.id, {"projektkod": "NINCS-ILYEN-KOD-XYZ"})
    with pytest.raises(cf.FeladatHiba):
        cf.letrehoz(db, admin, v.id, {"tipus": "utalas"})
    assert cf.elvet(db, admin, v.id)["allapot"] == "elvetve"
    _, v3 = cf.kozvetlen(db, admin, b, "Utald el a díjat")
    assert v3.adat["tipus"] == "feladat_elutasitva" and "feladat_javaslat" not in v3.adat


def test_api_idegen_uzenet_404_es_letrehozas(db, admin):
    from fastapi.testclient import TestClient

    from app.admin_agent import beszelgetes as bz
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    masik = db.scalar(select(Employee).where(Employee.id != admin.id).order_by(Employee.id))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    eredeti = db.commit
    db.commit = db.flush
    try:
        c = TestClient(app)
        bid = c.post("/api/v1/admin-agent/chat", json={"mod": "kerdez"}).json()["id"]
        r = c.post(f"/api/v1/admin-agent/chat/{bid}/feladat", json={"szoveg": "Vedd fel feladatnak: TIG a Bodor (demó) Bt.-nek"})
        assert r.status_code == 200
        uid = r.json()["valasz"]["id"]
        r = c.post(f"/api/v1/admin-agent/chat/uzenet/{uid}/feladat", json={"modositott": {"cim": "TIG a Bodor (demó) Bt.-nek"}})
        assert r.status_code == 200 and r.json()["allapot"] == "letrehozva"
        if masik is not None:
            ib = bz.uj(db, masik)
            _, iv = cf.kozvetlen(db, masik, ib, "Vedd fel feladatnak: valami (demó)")
            assert c.post(f"/api/v1/admin-agent/chat/uzenet/{iv.id}/feladat", json={}).status_code == 404
    finally:
        db.commit = eredeti
        app.dependency_overrides.clear()
