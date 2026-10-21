"""Lara — diszpó brief + technikai lista a tapasztalatból, és összefogó
adminisztrációs feladatok.

Rollbackes Postgres-teszt, minden demó adat "(demó)" jelölésű és a végén
visszagörgetődik. Modell nélkül fut (a modell-ágat a teszt-adapter adja).

Amit rögzít:
- a hasonló korábbi forgatásokból súlyozott technikai csomag (küszöb, medián
  darabszám), foglalt eszköz helyett szabad helyettesítő;
- a brief csak a projekt saját adataiból + visszatérő instrukciókból áll, a
  diszpó alap-emlékeztetője a végén marad;
- a modell csak az eszköztörzsből választhat;
- végrehajtás: brief + eszközök a KÖZÖS foglalási úton + „Technika ready”
  (technikai lista szöveg a projekten), a módosult brief nem íródik felül, és
  a visszavonás mindent visszaállít;
- a hatáskör: brief/technika igen, diszpó-kiküldés nem;
- összefogó feladat: időszak-értelmezés, élő terv a teljes rendszerből,
  idempotens részfeladat-bontás, előrehaladás."""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.admin_agent import chat_feladat as cf
from app.admin_agent import diszpo_tervezo as dt
from app.admin_agent import osszefogo
from app.models.admin_agent import AdminTask, Approval, MemoryChunk, TrustPolicy
from app.models.client import Client
from app.models.employee import Employee, EmployeeType
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.vallalkozas import Vallalkozas
from app.services.diszpo_sablon import BRIEF_SABLON

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

    # A jóváhagyó Lara felelőse (csak ő dönthet Lara javaslatairól).
    e = lara_felelos(db) or db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin.")
    return e


def _kod(db, client) -> ProjectCode:
    pc = ProjectCode(projektkod=f"DEMO{MA.year % 100:02d}-{random.randint(10000, 99999)}", client_id=client.id)
    db.add(pc)
    db.flush()
    return pc


def _eszkoz(db, nev, kat, mod=TrackMode.ASSET, keszlet=None, zoom=None) -> Equipment:
    e = Equipment(nev=nev, kategoria=kat, track_mode=mod, osszes_mennyiseg=keszlet, zoom_atfogas=zoom, hasznalhato="Használható")
    db.add(e)
    db.flush()
    return e


VISSZATERO = "Kérjük, mindenki fekete, logó nélküli ruhában érkezzen a forgatásra"


@pytest.fixture()
def tapasztalat(db):
    """Három korábbi forgatás ugyanannak az ügyfélnek, ugyanazzal a technikával,
    plus egy ütköző forgatás a célnapon és a cél-forgatás."""
    ugyfel = Client(nev=f"Fénykép (demó) Ügyfél {random.randint(1000, 9999)}")
    db.add(ugyfel)
    db.flush()
    kamera = _eszkoz(db, "Sony FX6 (demó)", "Kamera")
    optika = _eszkoz(db, "Sony 24-70 GM (demó)", "Optika", zoom="24-70 (demó)")
    optika2 = _eszkoz(db, "Sigma 24-70 Art (demó)", "Optika", zoom="24-70 (demó)")
    akku = _eszkoz(db, "BP-U60 akku (demó)", "Akkumulátor", TrackMode.STOCK, keszlet=20)
    dron = _eszkoz(db, "DJI Mavic (demó)", "Drón")
    korabbiak = []
    for i, db_akku in enumerate((4, 4, 6)):
        p = Project(
            nev=f"(demó) Termékfotózás stúdió {i}", project_code_id=_kod(db, ugyfel).id,
            forgatas_datuma=MA - timedelta(days=40 + 10 * i), helyszin="Budapest (demó) stúdió",
            brief=f"{VISSZATERO}\nÉrkezés 0{7 + i}:00-kor a (demó) portára\n\n{BRIEF_SABLON}",
        )
        db.add(p)
        db.flush()
        db.add_all([Assignment(project_id=p.id, equipment_id=kamera.id, qty=1),
                    Assignment(project_id=p.id, equipment_id=optika.id, qty=1),
                    Assignment(project_id=p.id, equipment_id=akku.id, qty=db_akku)])
        if i == 0:
            db.add(Assignment(project_id=p.id, equipment_id=dron.id, qty=1))
        korabbiak.append(p)
    cel_nap = MA + timedelta(days=5)
    utkozo = Project(nev="(demó) Másik forgatás", forgatas_datuma=cel_nap)
    db.add(utkozo)
    db.flush()
    db.add(Assignment(project_id=utkozo.id, equipment_id=optika.id, qty=1))
    cel = Project(nev="(demó) Termékfotózás stúdió új", project_code_id=_kod(db, ugyfel).id,
                  forgatas_datuma=cel_nap, helyszin="Budapest (demó) stúdió",
                  description="Új termékcsalád fotózása (demó).", brief=BRIEF_SABLON)
    db.add(cel)
    db.flush()
    db.expire_all()
    return {"ugyfel": ugyfel, "kamera": kamera, "optika": optika, "optika2": optika2, "akku": akku, "dron": dron,
            "korabbiak": korabbiak, "cel": db.get(Project, cel.id)}


# ── Tapasztalat + tervezet ───────────────────────────────────────────────────


def test_technika_csomag_tapasztalatbol_helyettesitovel(db, tapasztalat):
    k = tapasztalat
    hasonlok = dt.hasonlo_forgatasok(db, k["cel"])
    assert {h["project"].id for h in hasonlok} >= {p.id for p in k["korabbiak"]}
    assert "ugyanaz az ügyfél" in hasonlok[0]["okok"]
    csomag = dt.technika_javaslat(db, k["cel"], hasonlok)
    t = {x["equipment_id"]: x for x in csomag["tetelek"]}
    assert k["kamera"].id in t and t[k["kamera"].id]["forras"] == "tapasztalat"
    assert t[k["akku"].id]["qty"] == 4  # a 4, 4, 6 medián
    assert k["dron"].id not in t  # csak 1/3 forgatáson volt
    # A foglalt optika helyett az azonos zoom-tartományú, szabad helyettesítő.
    assert k["optika"].id not in t
    assert t[k["optika2"].id]["forras"] == "helyettesito"
    assert t[k["optika2"].id]["helyettesiti"]["equipment_id"] == k["optika"].id


def test_brief_szabaly_alapon_csak_sajat_adat_es_visszatero(db, tapasztalat):
    ter = dt.diszpo_tervezet(db, tapasztalat["cel"])
    brief = ter["payload"]["brief"]["uj"]
    assert tapasztalat["cel"].nev in brief and "Új termékcsalád fotózása" in brief
    assert VISSZATERO in brief
    assert "portára" not in brief  # projektfüggő (számos) sor nem kerül át
    assert brief.rstrip().endswith(BRIEF_SABLON.splitlines()[-1])
    assert ter["modell"]["allapot"] == "beallitas_szukseges"
    assert ter["payload"]["technika"] and dt.validate_diszpo(ter["payload"]) == []


def test_modell_csak_eszkoztorzsbol_valaszthat(db, tapasztalat):
    from app.admin_agent import llm

    k = tapasztalat
    llm.teszt_adapter(lambda r, sz, s: {
        "brief": "Stúdiófotózás (demó) — részletek a leírás szerint.",
        "technika": [{"equipment_id": 987654321, "qty": 1, "indoklas": "kitalált"},
                     {"equipment_id": k["kamera"].id, "qty": 1, "indoklas": "tapasztalat"},
                     {"equipment_id": k["dron"].id, "qty": 1, "indoklas": "a leírás szerint kell"}],
        "indoklas": "demó",
    })
    ter = dt.diszpo_tervezet(db, k["cel"])
    idk = {t["equipment_id"] for t in ter["payload"]["technika"]}
    assert 987654321 not in idk and k["kamera"].id in idk and k["dron"].id in idk
    assert any("nem létező" in f for f in ter["modell"]["figyelmeztetesek"])
    assert ter["payload"]["brief"]["uj"].rstrip().endswith(BRIEF_SABLON.splitlines()[-1])


def _trust_l1(db) -> None:
    for tp in db.scalars(select(TrustPolicy).where(TrustPolicy.tipus == "diszpo")).all():
        db.delete(tp)
    db.flush()
    db.add(TrustPolicy(tipus="diszpo", altipus=None, szint="L1"))
    db.flush()


def _vegrehajtas(db, admin, task):
    from app.admin_agent.executor import execute_approved
    from app.admin_agent.proposals import keszit_javaslat
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.module_enabled, s.side_effects_enabled, s.kill_switch = True, True, False
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id}
    _trust_l1(db)
    ter = dt.diszpo_tervezet(db, db.get(Project, task.project_id))
    p, dontes = keszit_javaslat(db, task, eszkoz=ter["eszkoz"], payload=ter["payload"], trigger="tervezet")
    a = db.scalar(select(Approval).where(Approval.proposal_id == p.id))
    assert a is not None, dontes.reason
    a.allapot = "approved"
    db.flush()
    return p, execute_approved(db, a, approver=admin)


def test_vegrehajtas_hozzarendel_technika_ready_es_visszavonas(db, admin, tapasztalat):
    k = tapasztalat
    cel = k["cel"]
    task = AdminTask(tipus="diszpo", cim="Diszpó (demó)", allapot="new", trust_level="L1", project_id=cel.id,
                     project_code_id=cel.project_code_id)
    db.add(task)
    db.flush()
    _, ex = _vegrehajtas(db, admin, task)
    assert ex.allapot == "succeeded", ex.eredmeny
    db.refresh(cel)
    foglalt = {a.equipment_id: a for a in db.scalars(select(Assignment).where(Assignment.project_id == cel.id))}
    assert set(foglalt) == {k["kamera"].id, k["optika2"].id, k["akku"].id}
    assert foglalt[k["akku"].id].qty == 4 and foglalt[k["kamera"].id].kivitel_datuma == cel.forgatas_datuma
    # A „Technika ready” lefutott: a technikai lista szövege a projekten van.
    assert "Kamera" in cel.technika_lista and "- 4db BP-U60 akku (demó)" in cel.technika_lista
    assert cel.backend_statusz == "OK" and VISSZATERO in cel.brief

    ki = dt.visszavonas(db, ex.eredmeny)
    assert ki["torolt_foglalas"] == 3 and ki["brief"] == "visszaallitva"
    db.refresh(cel)
    assert db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == cel.id)) == 0
    assert cel.brief == BRIEF_SABLON


def test_modosult_brief_nem_irodik_felul(db, admin, tapasztalat):
    from app.admin_agent.executor import execute_approved
    from app.admin_agent.proposals import keszit_javaslat
    from app.admin_agent.settings_service import get_settings

    cel = tapasztalat["cel"]
    task = AdminTask(tipus="diszpo", cim="Diszpó (demó)", allapot="new", trust_level="L1", project_id=cel.id)
    db.add(task)
    db.flush()
    s = get_settings(db)
    s.module_enabled, s.side_effects_enabled, s.kill_switch = True, True, False
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id}
    _trust_l1(db)
    ter = dt.diszpo_tervezet(db, cel)
    p, _ = keszit_javaslat(db, task, eszkoz=ter["eszkoz"], payload=ter["payload"], trigger="tervezet")
    cel.brief = "Közben kézzel megírt brief (demó)."
    a = db.scalar(select(Approval).where(Approval.proposal_id == p.id))
    a.allapot = "approved"
    db.flush()
    ex = execute_approved(db, a, approver=admin)
    assert ex.allapot == "failed" and "módosult" in ex.eredmeny["hiba"]
    assert cel.brief == "Közben kézzel megírt brief (demó)."
    assert db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == cel.id)) == 0


def test_tanulas_tudastarba(db, tapasztalat):
    from collections import Counter

    stat: Counter = Counter()
    assert dt.tanul(db, stat) >= 1
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"diszpo:ugyfel:{tapasztalat['ugyfel'].id}"))
    assert m is not None and m.hatokor == "diszpo"
    assert "Sony FX6 (demó)" in m.tartalom and VISSZATERO in m.tartalom and "DJI Mavic" not in m.tartalom


# ── Hatáskör + felismerés ────────────────────────────────────────────────────


def test_hataskor_es_felismeres():
    assert cf.felismer("Készítsd el a holnapi forgatás diszpójához a briefet és a technikai listát")["tipus"] == "diszpo"
    assert cf.hataskoron_kivul("Írd meg a diszpó briefjét a pénteki forgatásra") is None
    assert "briefet" in cf.hataskoron_kivul("Küldd ki a diszpót a stábnak")
    assert cf.hataskoron_kivul("Rakd át a diszpót holnapra") is not None
    assert cf.felismer("Zárd le az összes szeptemberi forgatás papírjait")["tipus"] == "osszefogo"
    assert cf.felismer("Intézd el, hogy a Kovács (demó) Kft. küldjön TIG-et péntekig.")["tipus"] == "tig"
    assert cf.felismer("Írj egy levelet a könyvelőnek a szeptemberi számlákról")["tipus"] == "email"


def test_idoszak_ertelmezes():
    ma = date(2026, 9, 28)
    assert osszefogo.idoszak("zárd le a szeptemberi forgatásokat", ma) == {"tol": "2026-09-01", "ig": "2026-09-30", "cimke": "2026. szeptember"}
    assert osszefogo.idoszak("a novemberi projektek", ma)["tol"] == "2025-11-01"  # még nem volt idén
    assert osszefogo.idoszak("múlt hónap összes TIG-je", ma)["tol"] == "2026-08-01"
    assert osszefogo.idoszak("Q3 papírozás", ma) == {"tol": "2026-07-01", "ig": "2026-09-30", "cimke": "2026. Q3"}
    assert osszefogo.idoszak("jövő heti forgatások", ma)["tol"] == "2026-10-05"
    assert osszefogo.idoszak("2026-08-03 és 2026-08-20 között", ma)["ig"] == "2026-08-20"
    assert osszefogo.idoszak("minden hiányzó TIG", ma) is None


# ── Összefogó feladat ────────────────────────────────────────────────────────


@pytest.fixture()
def papirozando(db):
    """Egy 10 napja lezajlott forgatás, egy külsős stábtaggal, akit egy demó
    vállalkozás számláz - se szerződés, se TIG."""
    v = Vallalkozas(nev="Összefogó (demó) Kft.", adoszam=f"{random.randint(10_000_000, 99_999_999)}-2-42")
    ember = Employee(full_name="Operatőr (demó) Ottó", tipus=EmployeeType.KULSOS)
    ugyfel = Client(nev=f"Zebra{random.randint(1000, 9999)} (demó) Zrt.")
    db.add_all([v, ember, ugyfel])
    db.flush()
    pc = _kod(db, ugyfel)
    nap = MA - timedelta(days=10)
    p = Project(nev="(demó) Összefogó forgatás", project_code_id=pc.id, forgatas_datuma=nap, diszpo="Kiküldve")
    p.crew.append(ember)
    db.add(p)
    db.flush()
    db.add(ProjectSzamlazo(project_id=p.id, employee_id=ember.id, szamlazo_vallalkozas_id=v.id))
    jovo = Project(nev="(demó) Jövő heti forgatás", project_code_id=pc.id, forgatas_datuma=MA + timedelta(days=3),
                   brief=BRIEF_SABLON)
    db.add(jovo)
    db.flush()
    db.expire_all()
    return {"p": db.get(Project, p.id), "pc": pc, "ugyfel": ugyfel, "jovo": jovo, "nap": nap}


def test_osszefogo_terv_bontas_elorehaladas(db, admin, papirozando):
    k = papirozando
    t = AdminTask(tipus="osszefogo", allapot="new", trust_level="L0", felelos_id=admin.id,
                  cim=f"Zárd le a(z) {k['pc'].projektkod} papírjait és készítsd elő a briefeket")
    db.add(t)
    db.flush()
    o = osszefogo.ertelmez(db, t)
    assert [x["kod"] for x in o["hatokor"]["projektkodok"]] == [k["pc"].projektkod]
    assert {"szerzodes", "tig", "szamla", "diszpo"} <= set(o["hatokor"]["temak"])
    assert t.project_code_id is None  # az összefogó feladat nem egy kódhoz kötött

    terv = osszefogo.terv(db, t)
    kulcsok = {x["kulcs"].split(":")[0] for x in terv["tetelek"]}
    assert {"szerzodes", "tig", "diszpo"} <= kulcsok
    assert all(x.get("project_code_id") == k["pc"].id for x in terv["tetelek"])

    ki = osszefogo.bontas(db, t, admin)
    assert ki["letrehozva"] == 3 and ki["mar_megvolt"] == 0
    reszek = db.scalars(select(AdminTask).where(AdminTask.parent_task_id == t.id)).all()
    assert {r.tipus for r in reszek} == {"szerzodes", "tig", "diszpo"}
    diszpo = next(r for r in reszek if r.tipus == "diszpo")
    assert diszpo.project_id == k["jovo"].id
    assert all(r.project_code_id == k["pc"].id for r in reszek)
    # Idempotens.
    assert osszefogo.bontas(db, t, admin)["letrehozva"] == 0

    a = osszefogo.frissites(db, t)
    assert a["reszfeladat_db"] == 3 and a["kesz"] is False and a["bontatlan_tetel_db"] == 0

    # Hatókör-szűkítés: csak TIG → a terv csak TIG-tételt tartalmaz.
    osszefogo.hatokor_modositas(db, t, {"temak": ["tig"]})
    assert {x["tema"] for x in osszefogo.terv(db, t)["tetelek"]} == {"tig"}
    with pytest.raises(osszefogo.OsszefogoHiba):
        osszefogo.hatokor_modositas(db, t, {"projektkodok": ["NINCS99-0000"]})


def test_osszefogo_idoszak_szures(db, admin, papirozando):
    t = AdminTask(tipus="osszefogo", allapot="new", trust_level="L0", cim="Nézd át az összes TIG-et 2019 januárjára")
    db.add(t)
    db.flush()
    osszefogo.ertelmez(db, t)
    assert all(x["project_id"] != papirozando["p"].id for x in osszefogo.terv(db, t)["tetelek"])


def test_api_diszpo_es_osszefogo(db, admin, tapasztalat, papirozando):
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
        cel = tapasztalat["cel"]
        r = c.get(f"/api/v1/admin-agent/diszpo/{cel.id}/tapasztalat")
        assert r.status_code == 200 and r.json()["technika"]["tetelek"]
        elotte = db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == cel.id))
        r = c.post(f"/api/v1/admin-agent/diszpo/{cel.id}/tervezet", json={"brief": True, "technika": True})
        assert r.status_code == 200, r.text
        assert r.json()["task"]["tipus"] == "diszpo" and r.json()["task"]["project_id"] == cel.id
        # Csak javaslat: a projekthez még semmi nem lett hozzárendelve.
        assert db.scalar(select(func.count(Assignment.id)).where(Assignment.project_id == cel.id)) == elotte

        r = c.post("/api/v1/admin-agent/tasks", json={"tipus": "osszefogo",
                                                      "cim": f"Zárd le a {papirozando['pc'].projektkod} papírjait"})
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        a = c.get(f"/api/v1/admin-agent/tasks/{tid}/osszefogo").json()
        assert a["nyitott_tetel_db"] >= 2 and a["reszfeladat_db"] == 0
        assert c.post(f"/api/v1/admin-agent/tasks/{tid}/osszefogo/bontas").json()["letrehozva"] >= 2
        assert c.get(f"/api/v1/admin-agent/tasks/{tid}/osszefogo").json()["bontatlan_tetel_db"] == 0
    finally:
        db.commit = eredeti
        app.dependency_overrides.clear()
