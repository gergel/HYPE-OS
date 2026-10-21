"""Lara eszköz-ismerete, szerep szerinti technikai csomag és a diszpó szövegének tanulása.

Rollbackes Postgres-teszt, minden demó adat "(demó)" jelölésű. Modell nélkül
fut; a modell-ágat a teszt-adapter adja.

Amit rögzít:
- a szabály alapú felismerés: szerep, altípus, gyújtótáv, fényerő; a hasonló
  átfogású optikák (24-70 ~ 28-75 ~ 24-105) hasonlók, a telezoom nem;
- a technikai csomag SZEREPET tanul: a foglalt kamera helyett másik cinema
  kamera (nem fotós gép), a foglalt optika helyett hasonló átfogású, és a
  szokásos darabszám (két kamera);
- a diszpó szövege: az időpontok a forgatás kezdetéhez mért tanult eltolásból,
  a szokás-mezők a hasonló diszpókból; végrehajtás + visszavonás;
- emberi javítás > modell > szabály; a modell csak valid profilt írhat."""

from __future__ import annotations

import random
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.admin_agent import diszpo_tervezo as dt
from app.admin_agent import eszkoz_ismeret as ei
from app.models.admin_agent import Approval, EszkozProfil, TrustPolicy
from app.models.client import Client
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.services.diszpo_sablon import DISZPO_SZOVEG_SABLON

MA = date.today()


@pytest.fixture()
def db(monkeypatch):
    from app.admin_agent import llm
    from app.core.config import settings
    from app.core.database import SessionLocal

    monkeypatch.setattr(settings, "gemini_api_key", None, raising=False)
    llm.teszt_adapter(None)
    try:
        sess = SessionLocal()
        sess.execute(select(1))
    except OperationalError:
        pytest.skip("Postgres nem elérhető — integrációs teszt kihagyva.")
    try:
        yield sess
    finally:
        llm.teszt_adapter(None)
        sess.rollback()
        sess.close()


@pytest.fixture()
def admin(db):
    from app.admin_agent.settings_service import lara_felelos

    e = lara_felelos(db) or db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin.")
    return e


def _e(nev, kat=None, zoom=None):
    return SimpleNamespace(nev=nev, kategoria=kat, zoom_atfogas=zoom, track_mode=TrackMode.ASSET)


# ── Szabály alapú felismerés ─────────────────────────────────────────────────


def test_szabaly_alapu_felismeres_es_hasonlosag():
    p = {n: ei.profil_szabaly(_e(n, k)) for n, k in [
        ("Sony FX6 (demó)", "Kamera"), ("Sony FX3 (demó)", "Kamera"), ("Canon EOS R5 (demó)", "Kamera"),
        ("Sony FE 24-70mm F2.8 GM II (demó)", "Optika"), ("Tamron 28-75mm F2.8 (demó)", "Optika"),
        ("Sony FE 24-105 F4 G (demó)", "Optika"), ("Sony 70-200 GM (demó)", "Optika"), ("Sigma 35mm f1.4 (demó)", "Optika"),
        ("Rode NTG-3 (demó)", "Hang"), ("DJI Mic 2 (demó)", "Hang"), ("Sony BP-U60 akku (demó)", "Akkumulátor"),
        ("Aputure LS 600d (demó)", "Világítás"), ("DJI RS 3 Pro (demó)", None),
    ]}
    assert p["Sony FX6 (demó)"]["csoport"] == "kamera:cinema" and p["Canon EOS R5 (demó)"]["csoport"] == "kamera:foto"
    o = p["Sony FE 24-70mm F2.8 GM II (demó)"]
    assert (o["csoport"], o["gyujto_min"], o["gyujto_max"], o["fenyero"], o["bajonett"]) == ("optika:standard_zoom", 24, 70, 2.8, "E")
    assert p["Sigma 35mm f1.4 (demó)"]["csoport"] == "optika:wide_fix"
    assert p["Sony 70-200 GM (demó)"]["csoport"] == "optika:tele_zoom"
    assert p["Rode NTG-3 (demó)"]["csoport"] == "hang:puska" and p["DJI Mic 2 (demó)"]["csoport"] == "hang:lavalier"
    assert p["Sony BP-U60 akku (demó)"]["csoport"] == "akkumulator:bpu"
    assert p["DJI RS 3 Pro (demó)"]["csoport"] == "mozgato:gimbal"  # kategória nélkül, a névből
    assert "interjú" in p["DJI Mic 2 (demó)"]["mire_jo"]
    h = ei.hasonlosag
    assert h(o, p["Tamron 28-75mm F2.8 (demó)"]) >= 0.75 and h(o, p["Sony FE 24-105 F4 G (demó)"]) >= 0.7
    assert h(o, p["Sony 70-200 GM (demó)"]) < 0.5 and h(o, p["Sigma 35mm f1.4 (demó)"]) < 0.3
    assert h(p["Sony FX6 (demó)"], p["Sony FX3 (demó)"]) == 1.0 and h(p["Sony FX6 (demó)"], p["Canon EOS R5 (demó)"]) < 0.3
    assert h(p["Rode NTG-3 (demó)"], p["DJI Mic 2 (demó)"]) < 0.5


# ── Szerep szerinti technikai csomag ─────────────────────────────────────────


def _eszkoz(db, nev, kat, mod=TrackMode.ASSET, keszlet=None) -> Equipment:
    e = Equipment(nev=nev, kategoria=kat, track_mode=mod, osszes_mennyiseg=keszlet, hasznalhato="Használható")
    db.add(e)
    db.flush()
    return e


def _kod(db, client) -> ProjectCode:
    pc = ProjectCode(projektkod=f"DEMO{MA.year % 100:02d}-{random.randint(10000, 99999)}", client_id=client.id)
    db.add(pc)
    db.flush()
    return pc


DISZPO_MINTA = """Érkezés a stúdióba: {studio}
Indulás a stúdióból: {indulas}
Érkezés a helyszínre: {helyszin}
Közlekedés: céges kisbusszal (demó)

Dresscode: {dresscode}

Catering: {catering}

Timing/menetrend:
{kezdes} forgatás kezdete (demó)"""


def _hhmm(t: time, perc: int) -> str:
    m = t.hour * 60 + t.minute + perc
    return f"{m // 60:02d}:{m % 60:02d}"


@pytest.fixture()
def k(db):
    ugyfel = Client(nev=f"Szerep (demó) Ügyfél {random.randint(1000, 9999)}")
    db.add(ugyfel)
    db.flush()
    e = {n: _eszkoz(db, f"{n} (demó)", kat) for n, kat in [
        ("Sony FX6", "Kamera"), ("Sony FX3", "Kamera"), ("Sony FX30", "Kamera"), ("Canon EOS R5", "Kamera"),
        ("Sony FE 24-70mm F2.8 GM", "Optika"), ("Tamron 28-75mm F2.8", "Optika"), ("Sony 70-200mm GM", "Optika"),
        ("Rode NTG-3", "Hang"),
    ]}
    e["akku"] = _eszkoz(db, "Sony BP-U60 akku (demó)", "Akkumulátor", TrackMode.STOCK, 30)
    kezdesek = (time(10, 0), time(9, 0), time(14, 0))
    korabbiak = []
    for i, kezd in enumerate(kezdesek):
        p = Project(
            nev=f"(demó) Interjú forgatás {i}", project_code_id=_kod(db, ugyfel).id, forgatas_datuma=MA - timedelta(days=30 + 7 * i),
            forgatas_kezdes_ido=kezd,
            diszpo_szovege=DISZPO_MINTA.format(
                studio=_hhmm(kezd, -120), indulas=_hhmm(kezd, -100), helyszin=_hhmm(kezd, -60), kezdes=_hhmm(kezd, 0),
                dresscode="fekete póló, zárt cipő (demó)" if i < 2 else "alkalmi (demó)",
                catering="nem biztosított (demó)" if i == 0 else "szendvics a helyszínen (demó)" if i == 1 else "ebéd (demó)",
            ),
        )
        db.add(p)
        db.flush()
        for n in ("Sony FX6", "Sony FX3", "Sony FE 24-70mm F2.8 GM", "Rode NTG-3"):
            db.add(Assignment(project_id=p.id, equipment_id=e[n].id, qty=1))
        db.add(Assignment(project_id=p.id, equipment_id=e["akku"].id, qty=6))
        korabbiak.append(p)
    cel_nap = MA + timedelta(days=4)
    utkozo = Project(nev="(demó) Ütköző forgatás", forgatas_datuma=cel_nap)
    db.add(utkozo)
    db.flush()
    for n in ("Sony FX6", "Sony FE 24-70mm F2.8 GM"):
        db.add(Assignment(project_id=utkozo.id, equipment_id=e[n].id, qty=1))
    cel = Project(nev="(demó) Interjú forgatás új", project_code_id=_kod(db, ugyfel).id, forgatas_datuma=cel_nap,
                  forgatas_kezdes_ido=time(15, 30), diszpo_szovege=DISZPO_SZOVEG_SABLON)
    db.add(cel)
    db.flush()
    db.expire_all()
    return {"e": e, "cel": db.get(Project, cel.id), "korabbiak": korabbiak}


def test_szerep_szerinti_csomag_masik_kamera_es_hasonlo_optika(db, k):
    e = k["e"]
    csomag = dt.technika_javaslat(db, k["cel"], dt.hasonlo_forgatasok(db, k["cel"]))
    t = {x["equipment_id"]: x for x in csomag["tetelek"]}
    # Két cinema kamera kell (a hasonló forgatásokon mindig kettő volt): az FX3
    # (szabad) + az FX6 helyett a hasonló FX30 - NEM a fotós R5.
    kamerak = [x for x in csomag["tetelek"] if x["csoport"] == "kamera:cinema"]
    assert {x["equipment_id"] for x in kamerak} == {e["Sony FX3"].id, e["Sony FX30"].id}
    assert e["Canon EOS R5"].id not in t and e["Sony FX6"].id not in t
    assert t[e["Sony FX3"].id]["forras"] == "tapasztalat"
    assert t[e["Sony FX30"].id]["forras"] == "helyettesito"
    # Optika: a foglalt 24-70 helyett a hasonló átfogású 28-75, nem a 70-200.
    assert t[e["Tamron 28-75mm F2.8"].id]["helyettesiti"]["equipment_id"] == e["Sony FE 24-70mm F2.8 GM"].id
    assert t[e["Tamron 28-75mm F2.8"].id]["hasonlosag"] >= 0.75 and e["Sony 70-200mm GM"].id not in t
    assert t[e["Rode NTG-3"].id]["csoport"] == "hang:puska" and "mire_jo" in t[e["Rode NTG-3"].id]
    assert t[e["akku"].id]["qty"] == 6


def test_diszpo_szoveg_tanulas_idoeltolassal(db, k):
    j = dt.diszpo_szoveg_javaslat(k["cel"], dt.hasonlo_forgatasok(db, k["cel"]))
    m = j["mezok"]
    # A kezdés (15:30) előtt 120 / 100 / 60 perccel - három korábbi diszpó alapján.
    assert m["érkezés a stúdióba"]["ertek"] == "13:30" and m["érkezés a helyszínre"]["ertek"] == "14:30"
    assert m["indulás a stúdióból"]["ertek"] == "13:50"
    assert m["dresscode"]["ertek"] == "fekete póló, zárt cipő (demó)"  # 2/3 diszpóban
    assert m["közlekedés"]["ertek"] == "céges kisbusszal (demó)"
    assert "catering" not in m  # háromféle érték - nincs szokás, a sablon marad
    assert "Érkezés a helyszínre: 14:30" in j["szoveg"] and "Timing/menetrend:" in j["szoveg"]
    assert dt.diszpo_szoveg_ures(DISZPO_SZOVEG_SABLON) and not dt.diszpo_szoveg_ures(j["szoveg"])
    # Kezdési idő nélkül az időpontok üresen maradnak, figyelmeztetéssel.
    k["cel"].forgatas_kezdes_ido = None
    j2 = dt.diszpo_szoveg_javaslat(k["cel"], dt.hasonlo_forgatasok(db, k["cel"]))
    assert "érkezés a helyszínre" not in j2["mezok"] and j2["figyelmeztetesek"]


def test_diszpo_szoveg_vegrehajtas_es_visszavonas(db, admin, k):
    from app.admin_agent.executor import execute_approved
    from app.admin_agent.proposals import keszit_javaslat
    from app.admin_agent.settings_service import get_settings
    from app.models.admin_agent import AdminTask

    s = get_settings(db)
    s.module_enabled, s.side_effects_enabled, s.kill_switch = True, True, False
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id}
    for tp in db.scalars(select(TrustPolicy).where(TrustPolicy.tipus == "diszpo")).all():
        db.delete(tp)
    db.flush()
    db.add(TrustPolicy(tipus="diszpo", altipus=None, szint="L1"))
    cel = k["cel"]
    task = AdminTask(tipus="diszpo", cim="Diszpó (demó)", allapot="new", trust_level="L1", project_id=cel.id)
    db.add(task)
    db.flush()
    ter = dt.diszpo_tervezet(db, cel, brief=False, technika=True, diszpo_szoveg=True)
    assert ter["payload"]["diszpo_szoveg"]["mezok"]["érkezés a helyszínre"]["ertek"] == "14:30"
    p, _ = keszit_javaslat(db, task, eszkoz=ter["eszkoz"], payload=ter["payload"], trigger="tervezet")
    a = db.scalar(select(Approval).where(Approval.proposal_id == p.id))
    a.allapot = "approved"
    db.flush()
    ex = execute_approved(db, a, approver=admin)
    assert ex.allapot == "succeeded", ex.eredmeny
    db.refresh(cel)
    assert "Érkezés a helyszínre: 14:30" in cel.diszpo_szovege and ex.eredmeny["diszpo_szoveg_frissitve"]
    assert db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == cel.id)) >= 4
    assert "Kamera" in cel.technika_lista
    ki = dt.visszavonas(db, ex.eredmeny)
    db.refresh(cel)
    assert ki["diszpo_szoveg"] == "visszaallitva" and cel.diszpo_szovege == DISZPO_SZOVEG_SABLON
    assert db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == cel.id)) == 0


def test_tanulas_szerepek_es_diszpo_szokasok(db, k):
    from collections import Counter

    from app.models.admin_agent import MemoryChunk

    dt.tanul(db, Counter())
    cid = k["cel"].project_code.client_id
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"diszpo:ugyfel:{cid}"))
    assert m is not None
    assert "cinema" in m.tartalom and "Optika – standard zoom" in m.tartalom
    assert "érkezés a helyszínre: a kezdés előtt ~60 perccel" in m.tartalom
    assert "dresscode: fekete póló" in m.tartalom


# ── Emberi javítás és AI-pontosítás ──────────────────────────────────────────


def test_ember_javitas_elsobbseg_es_ai_profilozas(db, admin):
    from app.admin_agent import llm

    obj = _eszkoz(db, "Rejtélyes objektív X (demó)", "Optika")
    lampa = _eszkoz(db, "Valami lámpa (demó)", "Világítás")
    assert ei.profil(db, obj)["altipus"] == "altalanos"
    llm.teszt_adapter(lambda r, sz, s: {"eszkozok": [
        {"id": obj.id, "funkcio": "optika", "altipus": None, "gyujto_min": 16, "gyujto_max": 35, "fenyero": 4,
         "mire_jo": "Ultraszéles zoom (demó)."},
        {"id": lampa.id, "funkcio": "urhajo", "mire_jo": "kitalált"},  # ismeretlen szerep - elutasítva
    ]})
    ki = ei.ai_profilozas(db, limit=500)
    assert ki["profilozva"] >= 1 and ki["elutasitva"] >= 1
    p = ei.profil(db, obj)
    assert (p["csoport"], p["forras"], p["mire_jo"]) == ("optika:ultrawide_zoom", "modell", "Ultraszéles zoom (demó).")
    assert ei.profil(db, lampa)["forras"] == "szabaly"
    # Az ember javítása a legerősebb - a modell újrafuttatva sem írja felül.
    ei.ember_javitas(db, obj, {"gyujto_min": 24, "gyujto_max": 105}, admin)
    ei.ai_profilozas(db, limit=500, ujra=True)
    p = ei.profil(db, obj)
    assert p["forras"] == "ember" and p["csoport"] == "optika:standard_zoom" and p["gyujto_max"] == 105
    with pytest.raises(ei.ProfilHiba):
        ei.ember_javitas(db, obj, {"gyujto_min": 200, "gyujto_max": 50}, admin)
    # Átnevezés után a modell-profil elavul (az emberi marad).
    t = db.scalar(select(EszkozProfil).where(EszkozProfil.equipment_id == obj.id))
    assert t.forras == "ember"


def test_api_eszkoz_ismeret(db, admin, k):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    eredeti = db.commit
    db.commit = db.flush
    try:
        c = TestClient(app)
        r = c.get("/api/v1/admin-agent/eszkozok/ismeret", params={"q": "(demó)", "funkcio": "optika"})
        assert r.status_code == 200 and all(x["funkcio"] == "optika" for x in r.json()["elemek"])
        eid = k["e"]["Sony FE 24-70mm F2.8 GM"].id
        r = c.get(f"/api/v1/admin-agent/eszkozok/{eid}/ismeret")
        assert r.status_code == 200
        assert r.json()["hasonlok"][0]["equipment_id"] == k["e"]["Tamron 28-75mm F2.8"].id
        r = c.patch(f"/api/v1/admin-agent/eszkozok/{eid}/profil", json={"mire_jo": "Fő interjú-optika (demó)."})
        assert r.status_code == 200 and r.json()["forras"] == "ember"
        assert c.patch(f"/api/v1/admin-agent/eszkozok/{eid}/profil", json={"funkcio": "urhajo"}).status_code == 400
        assert c.post("/api/v1/admin-agent/eszkozok/ai-profilozas", json={"limit": 5}).status_code == 400  # nincs modell
        r = c.get(f"/api/v1/admin-agent/diszpo/{k['cel'].id}/tapasztalat")
        assert r.json()["diszpo_szoveg"]["mezok"]["dresscode"]["ertek"] == "fekete póló, zárt cipő (demó)"
    finally:
        db.commit = eredeti
        app.dependency_overrides.clear()
