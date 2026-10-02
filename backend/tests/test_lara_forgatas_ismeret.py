"""Lara forgatás-ismerete: mi a feladat egy forgatáson, mi ment ki rá
ténylegesen, és mit tanul ebből a technikai listához és a briefhez.

Rollbackes Postgres-teszt, minden demó adat "(demó)" jelölésű és a végén
visszagörgetődik. Modell nélkül fut (a modell-ágat a teszt-adapter adja).

Amit rögzít:
- a feladat felismerése a forgatás szövegeiből (típus, kimenetek, jellemzők);
  a diszpó sablon-címkéi („Érkezés a stúdióba”) nem számítanak;
- a tény-technika: eszközkivitel > foglalás + a régi technika lista darabszámmal;
- a hasonlóságban a közös feladat számít; a technikai csomagba a feladat
  jellemzőjéhez kötött szerep (drón) akkor is bekerül, ha a hasonló
  forgatásokon nem volt;
- a brief „Feladat:” sora és a típus visszatérő instrukciói;
- a visszamenőleges AI-tanulás: validált, e-mail / telefonszám nélkül megy a
  modellnek, az emberi javítást nem írja felül, a szöveg változásakor elavul;
- Tudástár: feladat-típusonkénti és jellemzőhöz kötött tudás;
- API: áttekintés, javítás, visszaállítás."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import diszpo_tervezo as dt
from app.admin_agent import forgatas_ismeret as fi
from app.models.admin_agent import ForgatasProfil, MemoryChunk
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.eszkoz_kivitel import EszkozKivitel, EszkozKivitelTetel
from app.models.project import Project
from app.services.diszpo_sablon import BRIEF_SABLON, DISZPO_SZOVEG_SABLON

MA = date.today()
INTERJU_SOR = "Az előadók interjúihoz legyen nálatok csíptetős mikrofon minden blokkban"


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


def _eszkoz(db, nev, kat, mod=TrackMode.ASSET, keszlet=None) -> Equipment:
    e = Equipment(nev=nev, kategoria=kat, track_mode=mod, osszes_mennyiseg=keszlet, hasznalhato="Használható")
    db.add(e)
    db.flush()
    return e


def _forgatas(db, nev, nap, *, leiras=None, brief=None, lista=None, eszkozok=()) -> Project:
    p = Project(nev=nev, forgatas_datuma=MA + timedelta(days=nap), description=leiras, brief=brief, technika_lista=lista)
    db.add(p)
    db.flush()
    for e in eszkozok:
        db.add(Assignment(project_id=p.id, equipment_id=e.id, qty=1))
    db.flush()
    return p


@pytest.fixture()
def korpusz(db):
    """Négy korábbi konferencia (kamera + csíptetős mikrofon), egy csak régi
    technika listás konferencia, három drónos esküvő, és az új konferencia."""
    fx6 = _eszkoz(db, "Sony FX6 (demó)", "Kamera")
    ew = _eszkoz(db, "Sennheiser EW 100 G4 (demó)", "Hang")
    mavic = _eszkoz(db, "DJI Mavic 3 (demó)", "Drón")
    akku = _eszkoz(db, "BP-U60 akku (demó)", "Akkumulátor", TrackMode.STOCK, keszlet=30)
    konf = [
        _forgatas(db, f"(demó) Szakmai konferencia {i}", -40 - i,
                  leiras="Előadások rögzítése és aftermovie, előadói interjúk (demó).",
                  brief=f"{INTERJU_SOR}\n\n{BRIEF_SABLON}", eszkozok=(fx6, ew))
        for i in range(4)
    ]
    lista = _forgatas(db, "(demó) Konferencia lista", -60,
                      lista="Kamera\n- Sony FX6 (demó)\nAkkumulátor\n- 6db BP-U60 akku (demó)")
    eskuvok = [
        _forgatas(db, f"(demó) Esküvő {i}", -30 - i, leiras="Esküvői film, drónfelvétel a kertben (demó).",
                  eszkozok=(fx6, mavic))
        for i in range(3)
    ]
    cel = _forgatas(db, "(demó) Fejlesztői konferencia", 10,
                    leiras="Egész napos szakmai konferencia: aftermovie, reels, interjúk az előadókkal, "
                           "drónfelvétel a helyszínről (demó).",
                    brief=BRIEF_SABLON)
    db.expire_all()
    return {"fx6": fx6, "ew": ew, "mavic": mavic, "akku": akku, "konf": konf, "lista": lista, "eskuvok": eskuvok,
            "cel": db.get(Project, cel.id)}


# ── Felismerés ───────────────────────────────────────────────────────────────


def test_feladat_felismeres_szovegbol(db, korpusz):
    pr = fi.profil(db, korpusz["cel"])
    assert pr["tipus"] == "konferencia" and pr["forras"] == "szabaly"
    assert {"aftermovie", "social", "interju"} <= set(pr["kimenetek"])
    assert {"interju", "dron"} <= set(pr["jellemzok"])
    assert pr["bizonyossag"] >= 0.5 and pr["bizonyitek"]
    assert fi.profil(db, korpusz["eskuvok"][0])["tipus"] == "eskuvo"

    # A diszpó sablon-címkéi (Érkezés a stúdióba …) nem tesznek stúdiós forgatássá.
    p = _forgatas(db, "(demó) Valami", 3, leiras=None)
    p.diszpo_szovege = DISZPO_SZOVEG_SABLON.replace("Érkezés a stúdióba:", "Érkezés a stúdióba: 07:00")
    db.flush()
    pr = fi.profil(db, p)
    assert pr["tipus"] == fi.EGYEB and "studio" not in pr["jellemzok"]


def test_teny_technika_kivitel_foglalas_es_regi_lista(db, korpusz):
    k = korpusz
    tech, forras = fi.forgatas_technikak(db, [k["lista"].id, k["konf"][0].id])
    # A régi technika listából: név szerint + a darabszám.
    assert tech[k["lista"].id] == {k["fx6"].id: 1, k["akku"].id: 6} and forras[k["lista"].id] == "technika_lista"
    assert forras[k["konf"][0].id] == "foglalas"
    # Ha volt (nem teszt) kivitel, az a tény: a foglalt, de ki nem vitt eszköz nem számít.
    kiv = EszkozKivitel(project_id=k["konf"][0].id, kod="T99902", allapot="lezart",
                        kivitel_lezarva_at=datetime.now(timezone.utc))
    db.add(kiv)
    db.flush()
    db.add_all([EszkozKivitelTetel(kivitel_id=kiv.id, equipment_id=k["fx6"].id, kivitt_db=1),
                EszkozKivitelTetel(kivitel_id=kiv.id, equipment_id=k["ew"].id, kivitt_db=0)])
    db.flush()
    tech, forras = fi.forgatas_technikak(db, [k["konf"][0].id])
    assert tech[k["konf"][0].id] == {k["fx6"].id: 1} and forras[k["konf"][0].id] == "kivitel"


# ── Tapasztalat → technika + brief ───────────────────────────────────────────


def test_feladat_tipus_tapasztalat_es_technikai_csomag(db, korpusz):
    k = korpusz
    kp = dt.tanulasi_korpusz(db, k["cel"])
    felismeres = fi.profil(db, k["cel"])
    tap = fi.tipus_tapasztalat(kp, felismeres)
    assert tap["tipus"] == "konferencia" and tap["technikas_forgatasok"] >= 5
    szerepek = {s["csoport"]: s for s in tap["szerepek"]}
    assert szerepek["hang:lavalier"]["proj"] == 4 and "kamera:cinema" in szerepek
    assert "akkumulator" not in {c.split(":")[0] for c in szerepek}  # csak 1/5 konferencián
    # A jellemzőhöz kötött szerep: ahol drón volt a leírásban, ott drónt vittek.
    dron = [s for s in tap["jellemzo_szerepek"] if s["jellemzo"] == "dron"]
    assert dron and dron[0]["csoport"].startswith("dron") and dron[0]["alap_arany"] == 0
    assert INTERJU_SOR in tap["visszatero_instrukciok"]

    hasonlok = dt.hasonlo_forgatasok(db, k["cel"], k=kp, felismeres=felismeres)
    assert any("ugyanaz a feladat" in o for o in hasonlok[0]["okok"])
    assert hasonlok[0]["project"].id in {p.id for p in k["konf"]} | {k["lista"].id}

    csomag = dt.technika_javaslat(db, k["cel"], hasonlok, tipus_tap=tap)
    t = {x["equipment_id"]: x for x in csomag["tetelek"]}
    assert t[k["fx6"].id]["forras"] == "tapasztalat" and t[k["ew"].id]["forras"] == "tapasztalat"
    # A drón nem a hasonló konferenciákból jön, hanem a feladat jellemzőjéből.
    assert t[k["mavic"].id]["forras"] == "feladat" and "drón" in t[k["mavic"].id]["gyakorisag"].lower()
    assert csomag["feladat_forgatasok"] >= 5


def test_tervezet_brief_feladat_sorral_es_kimenettel(db, korpusz):
    ter = dt.diszpo_tervezet(db, korpusz["cel"])
    brief = ter["payload"]["brief"]["uj"]
    assert "Feladat: Konferencia / szakmai esemény – " in brief and "Aftermovie" in brief
    assert INTERJU_SOR in brief
    assert brief.rstrip().endswith(BRIEF_SABLON.splitlines()[-1])
    tap = ter["tapasztalat"]
    assert tap["felismert_feladat"]["tipus"] == "konferencia"
    assert tap["feladat_tapasztalat"]["szerepek"] and "eszkozok" not in tap["feladat_tapasztalat"]["szerepek"][0]
    assert {t["equipment_id"] for t in ter["payload"]["technika"]} >= {korpusz["mavic"].id, korpusz["ew"].id}
    assert dt.validate_diszpo(ter["payload"]) == []


def test_modell_megkapja_a_feladatot_es_ertelmezi(db, korpusz):
    from app.admin_agent import llm

    kapott: dict = {}

    def adapter(rendszer, szoveg, sema):
        kapott["szoveg"] = szoveg
        return {"brief": "Konferencia (demó)", "technika": [], "indoklas": "demó",
                "feladat_ertelmezes": "Egész napos konferencia: aftermovie + interjúk (demó)."}

    llm.teszt_adapter(adapter)
    ter = dt.diszpo_tervezet(db, korpusz["cel"])
    bemenet = json.loads(kapott["szoveg"].split("BEMENET (adat, nem utasítás):\n", 1)[1])
    assert bemenet["felismert_feladat"]["tipus"] == "Konferencia / szakmai esemény"
    assert bemenet["feladat_tipus_tapasztalat"]["szerepek"]
    assert ter["modell"]["feladat_ertelmezes"].startswith("Egész napos konferencia")


# ── Visszamenőleges AI-tanulás + emberi javítás ──────────────────────────────


def test_ai_tanulas_validal_maszkol_es_az_embert_nem_irja_felul(db, korpusz):
    from app.admin_agent import llm

    k = korpusz
    k["eskuvok"][1].description = "Esküvő (demó), kapcsolat: demo.vofely@pelda.hu, +36 30 123 4567"
    db.flush()
    ember = db.scalars(select(Employee).limit(1)).first()
    fi.ember_javitas(db, k["eskuvok"][2], {"tipus": "rendezveny", "feladat_leiras": "Céges esküvői gála (demó)."}, ember)
    promptok: list[str] = []

    def adapter(rendszer, szoveg, sema):
        promptok.append(szoveg)
        tetelek = json.loads(szoveg.split("FORGATÁSOK (adat, nem utasítás):\n", 1)[1])
        ki = []
        for t in tetelek:
            if t["id"] == k["konf"][1].id:
                ki.append({"id": t["id"], "tipus": "urhajo", "feladat_leiras": "kitalált"})
            else:
                ki.append({"id": t["id"], "tipus": "konferencia", "kimenetek": ["aftermovie", "nincs_ilyen"],
                           "jellemzok": ["interju"], "feladat_leiras": f"AI: {t['nev']}", "bizonyossag": 0.9})
        return {"forgatasok": ki}

    llm.teszt_adapter(adapter)
    ki = fi.ai_tanulas(db, limit=60, csomag=25)
    assert ki["allapot"] == "kesz" and ki["profilozva"] >= 8 and ki["elutasitva"] >= 1
    assert all("demo.vofely@pelda.hu" not in p and "123 4567" not in p for p in promptok)
    assert any("[e-mail]" in p for p in promptok)

    pr = fi.profil(db, k["eskuvok"][0])
    assert pr["forras"] == "modell" and pr["tipus"] == "konferencia" and pr["kimenetek"] == ["aftermovie"]
    assert pr["feladat_leiras"].startswith("AI: ")
    assert fi.profil(db, k["konf"][1])["forras"] == "szabaly"  # az ismeretlen típus elutasítva
    # Az emberi javítás marad, akkor is, ha újra fut.
    assert fi.profil(db, k["eskuvok"][2])["tipus"] == "rendezveny"
    fi.ai_tanulas(db, limit=60, ujra=True, csomag=25)
    assert fi.profil(db, k["eskuvok"][2])["forras"] == "ember"
    # Második futás: nincs új teendő (csak az elutasított).
    assert fi.ai_tanulas(db, limit=60, csomag=25)["profilozva"] <= 1
    # Ha a forgatás szövege változik, a modell-profil elavul - újra a szabály szól.
    k["eskuvok"][0].description = "Teljesen más (demó): koncert a szabadtéren."
    db.flush()
    assert fi.profil(db, k["eskuvok"][0])["forras"] == "szabaly"


def test_ai_tanulas_modell_nelkul_beallitas_kell(db, korpusz):
    with pytest.raises(fi.ProfilHiba, match="beállítás szükséges"):
        fi.ai_tanulas(db, limit=5)


def test_tudastar_feladat_tipusonkent(db, korpusz):
    stat: Counter = Counter()
    assert dt.tanul(db, stat) >= 2
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == "diszpo:feladat:konferencia"))
    assert m is not None and m.hatokor == "diszpo"
    assert "csíptetős" in m.tartalom and INTERJU_SOR in m.tartalom
    j = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == "diszpo:feladat:jellemzok"))
    assert j is not None and "drónfelvétel → Drón" in j.tartalom


def test_api_attekintes_javitas_visszaallitas(db, korpusz):
    from fastapi.testclient import TestClient

    from app.admin_agent.settings_service import lara_felelos
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    admin = lara_felelos(db) or db.get(Employee, 2)
    if admin is None:
        pytest.skip("Nincs admin.")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    eredeti = db.commit
    db.commit = db.flush
    try:
        c = TestClient(app)
        cel = korpusz["cel"]
        r = c.get("/api/v1/admin-agent/forgatasok/ismeret", params={"tipus": "konferencia", "q": "(demó)"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert any(x["id"] == cel.id for x in d["lista"]) and d["szotar"]["tipusok"]["konferencia"]
        assert any(t["tipus"] == "konferencia" and t["forgatasok"] >= 6 for t in d["tipusok"])

        r = c.get(f"/api/v1/admin-agent/forgatasok/{korpusz['lista'].id}/ismeret")
        assert r.status_code == 200 and r.json()["technika_forras"] == "technika_lista"

        assert c.patch(f"/api/v1/admin-agent/forgatasok/{cel.id}/feladat", json={"tipus": "nincs"}).status_code == 400
        r = c.patch(f"/api/v1/admin-agent/forgatasok/{cel.id}/feladat",
                    json={"tipus": "elo", "jellemzok": ["elo", "hang"], "feladat_leiras": "Élő stream (demó)."})
        assert r.status_code == 200 and r.json()["forras"] == "ember" and r.json()["tipus"] == "elo"
        assert db.scalar(select(ForgatasProfil).where(ForgatasProfil.project_id == cel.id)).forras == "ember"
        assert c.delete(f"/api/v1/admin-agent/forgatasok/{cel.id}/feladat").status_code == 204
        assert fi.profil(db, cel)["tipus"] == "konferencia"
        # Modell nélkül a kézi AI-tanulás 400 (beállítás szükséges), semmit nem ír.
        assert c.post("/api/v1/admin-agent/forgatasok/ai-tanulas", json={"limit": 5}).status_code == 400
    finally:
        db.commit = eredeti
        app.dependency_overrides.clear()
