"""Autó állapotfotók (a felhasználó kérése, 2026-10): bekérő linken hét kép
(négy oldal, csomagtartó, első és hátsó üléssor), autónként napokra bontva
visszanézhető. Egyelőre teszt jelleggel - a diszpóval nem megy ki.

A tárhelyet hamis függvények helyettesítik. Tranzakcióban fut a helyi
adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.auto import Auto
from app.models.auto_allapot import OLDAL_KULCSOK, AutoAllapotFoto
from app.models.employee import Employee, EmployeeType, SystemRole

A = "/api/v1/autok"
P = "/api/v1/public/auto-allapot"


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

    tarhely = {"fel": {}, "torolt": []}

    def fel(data, key, ct):
        tarhely["fel"][key] = (data, ct)
        return f"https://r2.example/{key}"

    monkeypatch.setattr(document_storage, "upload_bytes", fel)
    monkeypatch.setattr(document_storage, "delete_object", lambda key: tarhely["torolt"].append(key))
    admin = Employee(full_name="Autós Admin (demó)", tipus=EmployeeType.BELSOS, email="autos-admin-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    auto = Auto(rendszam="DEMO-001", megnevezes="Gyártásos busz (demó)", aktiv=True)
    db.add_all([admin, auto])
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    db.commit = db.flush
    try:
        yield {"c": TestClient(app), "db": db, "auto": auto, "tarhely": tarhely}
    finally:
        app.dependency_overrides.clear()


def _kep(szelesseg=40, magassag=20) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (szelesseg, magassag), "blue").save(buf, format="PNG")
    return buf.getvalue()


def _feltolt(c, token, oldal, nev="Sofőr (demó)"):
    return c.post(f"{P}/{token}/foto", data={"oldal": oldal, "keszito": nev},
                  files={"file": (f"{oldal}.png", _kep(), "image/png")})


def test_bekeres_link_hat_kep_es_allapot_oldal(k):
    c, auto = k["c"], k["auto"]
    r = c.post(f"{A}/{auto.id}/allapot/bekeres")
    assert r.status_code == 201, r.text
    token = r.json()["token"]

    adat = c.get(f"{P}/{token}").json()
    assert adat["rendszam"] == "DEMO-001" and [o["kulcs"] for o in adat["oldalak"]] == list(OLDAL_KULCSOK)
    assert len(adat["oldalak"]) == 7 and adat["mai_fotok"] == {}

    for oldal in OLDAL_KULCSOK:
        r = _feltolt(c, token, oldal)
        assert r.status_code == 200, r.text
    adat = c.get(f"{P}/{token}").json()
    assert set(adat["mai_fotok"]) == set(OLDAL_KULCSOK)
    # JPEG-be alakítva, bélyegképpel.
    kulcsok = list(k["tarhely"]["fel"])
    assert any(x.endswith("-kicsi.jpg") for x in kulcsok)
    assert all(ct == "image/jpeg" for _, ct in k["tarhely"]["fel"].values())

    allapot = c.get(f"{A}/{auto.id}/allapot").json()
    assert allapot["auto"]["rendszam"] == "DEMO-001"
    assert len(allapot["napok"]) == 1 and allapot["napok"][0]["db"] == 7 and allapot["napok"][0]["osszes"] == 7
    assert allapot["napok"][0]["fotok"]["csomagtarto"]["keszito"] == "Sofőr (demó)"
    assert allapot["bekeresek"][0]["mai_db"] == 7


def test_ujrafotozas_aznap_lecserel_masnap_megmarad(k):
    c, db, auto = k["c"], k["db"], k["auto"]
    token = c.post(f"{A}/{auto.id}/allapot/bekeres").json()["token"]
    elso = _feltolt(c, token, "eleje").json()
    masodik = _feltolt(c, token, "eleje").json()
    assert db.get(AutoAllapotFoto, elso["id"]) is None and db.get(AutoAllapotFoto, masodik["id"]) is not None
    assert k["tarhely"]["torolt"]  # a lecserélt kép a tárhelyről is megy

    # A tegnapi kép megmarad, és külön napként látszik.
    db.get(AutoAllapotFoto, masodik["id"]).keszult_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.flush()
    _feltolt(c, token, "eleje")
    napok = c.get(f"{A}/{auto.id}/allapot").json()["napok"]
    assert len(napok) == 2 and all(n["fotok"].get("eleje") for n in napok)


def test_uj_link_uj_kor_ures_es_a_regi_lezarul(k):
    """Minden link külön fotózási kör (a felhasználó jelezte, hogy az új link
    a régi aznapi képei miatt rögtön késznek látszott): az új link üresen
    indul, a régi élő link lezárul, és mindkét kör képei megmaradnak."""
    c, auto = k["c"], k["auto"]
    regi = c.post(f"{A}/{auto.id}/allapot/bekeres").json()
    for oldal in OLDAL_KULCSOK:
        _feltolt(c, regi["token"], oldal)
    assert len(c.get(f"{P}/{regi['token']}").json()["mai_fotok"]) == 7

    uj = c.post(f"{A}/{auto.id}/allapot/bekeres").json()
    assert uj["mai_db"] == 0
    assert c.get(f"{P}/{uj['token']}").json()["mai_fotok"] == {}
    assert c.get(f"{P}/{regi['token']}").status_code == 404  # a régi link lezárult

    # Az új kör ugyanarról a nézetről nem írja felül a régi kör képét.
    _feltolt(c, uj["token"], "eleje")
    assert list(c.get(f"{P}/{uj['token']}").json()["mai_fotok"]) == ["eleje"]
    allapot = c.get(f"{A}/{auto.id}/allapot").json()
    assert [b["visszavonva_at"] is None for b in allapot["bekeresek"]] == [True, False]
    korok = allapot["napok"]
    assert [(n["bekeres_id"], n["db"]) for n in korok] == [(uj["id"], 1), (regi["id"], 7)]
    assert korok[0]["datum"] == korok[1]["datum"]


def test_hibas_keres_es_visszavont_link(k):
    c, auto = k["c"], k["auto"]
    b = c.post(f"{A}/{auto.id}/allapot/bekeres").json()
    assert _feltolt(c, b["token"], "teto").status_code == 400  # nincs ilyen nézet
    r = c.post(f"{P}/{b['token']}/foto", data={"oldal": "eleje"}, files={"file": ("a.txt", b"szoveg", "text/plain")})
    assert r.status_code == 400
    assert c.delete(f"{A}/{auto.id}/allapot/bekeres/{b['id']}").status_code == 204
    assert c.get(f"{P}/{b['token']}").status_code == 404
    assert _feltolt(c, b["token"], "eleje").status_code == 404
    assert c.get(f"{P}/nincs-ilyen-token").status_code == 404


def test_admin_torolheti_a_fotot(k):
    c, db, auto = k["c"], k["db"], k["auto"]
    token = c.post(f"{A}/{auto.id}/allapot/bekeres").json()["token"]
    f = _feltolt(c, token, "csomagtarto").json()
    assert c.delete(f"{A}/{auto.id}/allapot/fotok/{f['id']}").status_code == 204
    assert db.get(AutoAllapotFoto, f["id"]) is None
    assert c.get(f"{A}/{auto.id}/allapot").json()["napok"] == []


def test_karosszeria_felismeres_es_beallitas(k):
    """A fotózási körvonal a karosszériától függ: beállítás nélkül a
    típusnévből ismeri fel (Bigster -> SUV, Trafic -> furgon, A4 ->
    személyautó), kézzel felülírható."""
    from types import SimpleNamespace

    from app.services.auto_allapot import karosszeria

    def kar(megnevezes, tipus=None, beallitott=None):
        return karosszeria(SimpleNamespace(megnevezes=megnevezes, tipus=tipus, karosszeria=beallitott))

    assert kar("Dacia Bigster") == ("suv", False)
    assert kar(None, "Renault Trafic") == ("furgon", False)
    assert kar("Régi Audi A4") == ("szemelyauto", False)
    assert kar("Dacia Bigster", beallitott="furgon") == ("furgon", True)

    c, auto = k["c"], k["auto"]
    # A demóautó "Gyártásos busz (demó)" -> furgon.
    assert c.get(f"{A}/{auto.id}/allapot").json()["auto"]["karosszeria"] == "furgon"
    r = c.put(f"{A}/{auto.id}/karosszeria", json={"karosszeria": "suv"})
    assert r.json() == {"karosszeria": "suv", "karosszeria_beallitva": True}
    token = c.post(f"{A}/{auto.id}/allapot/bekeres").json()["token"]
    assert c.get(f"{P}/{token}").json()["karosszeria"] == "suv"
    assert c.put(f"{A}/{auto.id}/karosszeria", json={"karosszeria": "hajo"}).status_code == 400
    assert c.put(f"{A}/{auto.id}/karosszeria", json={"karosszeria": None}).json()["karosszeria_beallitva"] is False
