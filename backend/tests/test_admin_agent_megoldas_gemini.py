"""Lara — megoldási javaslat a (kérdésekből született) javítási feladatokhoz, és
gyorsított tanulás a Geminivel (partner-profil, önreflexió).

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback.
Valódi modellhívás nincs (hamis adapter / hamis beszélgetés)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import gemini_tanulas, llm, megoldas, nyomozas
from app.admin_agent.onellenorzes import valaszol
from app.admin_agent.settings_service import get_settings
from app.models.admin_agent import AdminTask, LaraKerdes, LearningRun, MemoryChunk, PlaybookRule, SourceEvent
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
        nyomozas.teszt_beszelgetes(None)
        llm.teszt_adapter(None)
        sess.rollback()
        sess.close()


@pytest.fixture()
def admin(db):
    e = db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin munkatárs (#2) a teszthez.")
    return e


class _Hamis:
    def __init__(self, korok):
        self.korok = list(korok)

    def lepes(self):
        kor = self.korok.pop(0)
        return ([], kor) if isinstance(kor, str) else (kor, None)

    def eredmenyek(self, parok):
        pass


def _kerdes(db, tipus, kontextus, partner="Megoldás Teszt Kft.") -> LaraKerdes:
    k = LaraKerdes(tipus=tipus, allapot="nyitott", kulcs=f"meg|{tipus}", partner_nev=partner, kerdes="Miért?",
                   kontextus=kontextus)
    db.add(k)
    db.flush()
    return k


def test_minden_hibas_valasz_javitasi_feladat_megoldasi_lepesekkel(db):
    """Számla-, papír- és bővített kérdésnél is: „hibás" → javítási feladat,
    azonnali, linkes megoldási lépésekkel."""
    szamla = _kerdes(db, "szamla_besorolas", {"esetek": [{"bejovo_id": 1, "szamlaszam": "SZ-1", "vegso_szoveg": "működési",
                                                          "lara_szoveg": "új kiadás · DEMO"}]})
    e = valaszol(db, szamla, valasz_tipus="hibas", magyarazat="Rossz helyre ment.", user_id=2, elesithet=False)
    t = db.get(AdminTask, e["feladat_id"])
    lep = t.forras_referenciak["lara_megoldas"]["alap"]
    assert t.altipus == "javitas" and t.tipus == "egyeb" and t.forras_referenciak["lara_kerdes_id"] == szamla.id
    assert "SZ-1" in lep[0]["leiras"] and lep[0]["link"] == "/penzugyek/bejovo-szamlak"
    assert any("Rossz helyre ment." in x["leiras"] for x in lep)

    elt = _kerdes(db, "rendszer_elteres", {"ellenorzes": "fizetve_papir_nelkul", "cimke": "A megrendelő fizetett, de nincs papír",
                                           "esetek": [{"rekord": "projektkod:999", "projektkod": "MEG-1"}]})
    e2 = valaszol(db, elt, valasz_tipus="hibas", magyarazat=None, user_id=2, elesithet=False)
    lep2 = db.get(AdminTask, e2["feladat_id"]).forras_referenciak["lara_megoldas"]["alap"]
    assert "papír nélkül" in lep2[0]["leiras"] and "MEG-1" in lep2[0]["leiras"]


def test_ai_megoldas_konkret_lepesek_es_lathatosag(db, admin):
    """Lara saját javaslata (csak-olvasó eszközökkel): konkrét lépések, csak
    belső link; a modell-rész csak a futtatónak látszik, az alap mindenkinek."""
    k = _kerdes(db, "szamla_besorolas", {"esetek": [{"bejovo_id": 1, "szamlaszam": "SZ-2"}]})
    e = valaszol(db, k, valasz_tipus="hibas", magyarazat=None, user_id=2, elesithet=False)
    t = db.get(AdminTask, e["feladat_id"])
    rendszerek = []

    def gyar(rendszer, feladat, eszkozok):
        rendszerek.append((rendszer, feladat))
        return _Hamis([[("globalis_kereses", {"szoveg": "SZ-2"})], json.dumps({
            "osszefoglalo": "A számla a működési költségek közé került, de a DEMO projektkódé.",
            "lepesek": [{"leiras": "Nyisd meg az SZ-2 számlát és állítsd a célt új kiadásra.", "link": "/penzugyek/bejovo-szamlak"},
                        {"leiras": "Külső", "link": "https://rossz.example"}],
            "biztossag": 0.7, "figyelmeztetesek": []}, ensure_ascii=False)])

    nyomozas.teszt_beszelgetes(gyar)
    ai = megoldas.ai_megoldas(db, t, admin)
    assert "MEGOLDÁSI JAVASLATOT" in rendszerek[0][0] and "AZ AI ASSZISZTENS TUDÁSA" in rendszerek[0][0]
    assert "Lara egyik kérdéséből" in rendszerek[0][1]
    assert ai["allapot"] == "kesz" and [x["link"] for x in ai["lepesek"]] == ["/penzugyek/bejovo-szamlak", None]
    assert ai["vizsgalt"][0]["eszkoz"] == "globalis_kereses"
    assert megoldas.lathato_megoldas(t, admin)["ai"]["osszefoglalo"].startswith("A számla")
    masik = db.scalars(select(Employee).where(Employee.id != admin.id).limit(1)).first()
    if masik is not None:
        m = megoldas.lathato_megoldas(t, masik)
        assert "ai" not in m and m["alap"]


def test_hatter_megoldas_javitasi_feladat_elol_korlattal(db, admin):
    s = get_settings(db)
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id, "megoldas": True}
    for t in db.scalars(select(AdminTask).where(AdminTask.tipus == "egyeb")).all():
        t.allapot = "cancelled"
    kulso = AdminTask(tipus="egyeb", cim="Kívülről kapott feladat", allapot="new", trust_level="L0")
    db.add(kulso)
    db.flush()
    k = _kerdes(db, "szamla_besorolas", {"esetek": [{"bejovo_id": 1}]})
    jav = db.get(AdminTask, valaszol(db, k, valasz_tipus="hibas", magyarazat=None, user_id=2, elesithet=False)["feladat_id"])
    nyomozas.teszt_beszelgetes(lambda *_: _Hamis([json.dumps({"osszefoglalo": "x", "lepesek": [{"leiras": "y"}], "biztossag": 0.5})]))
    r = megoldas.futtat(db, max_db=1)
    assert r["keszult"] == 1 and "ai" in jav.forras_referenciak["lara_megoldas"]
    assert not (kulso.forras_referenciak or {}).get("lara_megoldas")
    nyomozas.teszt_beszelgetes(lambda *_: _Hamis([json.dumps({"osszefoglalo": "x", "lepesek": [{"leiras": "y"}], "biztossag": 0.5})]))
    assert megoldas.futtat(db, max_db=5)["keszult"] == 1  # a kívülről kapott is megkapja
    s.limitek = {**s.limitek, "megoldas": False}
    db.flush()
    assert megoldas.futtat(db)["allapot"] == "kikapcsolva"


def _partner_esetek(db, partner: str, n: int = 3) -> None:
    for i in range(n):
        azon = f"kiadas:gemteszt{i}"
        db.add(SourceEvent(forras="megfigyeles", forras_azonosito=azon, allapot="feldolgozva",
                           metaadat={"tabla": "kiadas", "partner": partner}))
        db.add(MemoryChunk(hatokor="szamla", tartalom=f"{partner} számlája a forgatás projektkódjára ment ({i}).",
                           forras=f"megfigyeles:{azon}", minosites="jovahagyott", ervenyes=True))
    db.flush()


def test_partner_profil_a_geminivel_jelolt_es_fuggo_szabaly(db):
    """≥3 jóváhagyott esetből profil-JELÖLT és FÜGGŐ szabályjavaslat; ugyanabból
    az anyagból nem hív újra; nem adminisztratív területre nem javasol."""
    hivasok = []

    def adapter(rendszer, szoveg, schema):
        hivasok.append(szoveg)
        return {"profil": "A számlái mindig a forgatás projektkódjára mennek.", "bizonytalansag": 0.2,
                "szabalyok": [{"hatokor": "szamla", "cim": "forgatás projektkódjára", "tartalom": "Új kiadás a forgatás kódjára."}]}

    llm.teszt_adapter(adapter)
    _partner_esetek(db, "Profilteszt Gemini Kft.")
    r = gemini_tanulas.partner_profilok(db, max_db=50)
    assert r.get("uj", 0) >= 1 and any("Profilteszt Gemini Kft." in h for h in hivasok)
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras.like("gemini:profil:profilteszt gemini%")))
    assert m is not None and not m.ervenyes and m.minosites == "jelolt" and "forgatás projektkódjára" in m.tartalom
    sz = db.scalar(select(PlaybookRule).where(PlaybookRule.cim.like("Profilteszt Gemini Kft.:%")))
    assert sz is not None and sz.allapot == "pending" and sz.feltetelek["forras"] == "gemini"
    elotte = len(hivasok)
    gemini_tanulas.partner_profilok(db, max_db=50)
    assert not any("Profilteszt Gemini Kft." in h for h in hivasok[elotte:])

    # Nem adminisztratív terület → séma-hiba → semmi nem jön létre (fail-closed).
    llm.teszt_adapter(lambda *_: {"profil": "x", "bizonytalansag": 0.1,
                                  "szabalyok": [{"hatokor": "diszpo", "cim": "c", "tartalom": "t"}]})
    _partner_esetek(db, "Diszpó Tiltott Kft.")
    gemini_tanulas.partner_profilok(db, max_db=50)
    assert db.scalar(select(MemoryChunk).where(MemoryChunk.forras.like("gemini:profil:diszpo tiltott%"))) is None


def test_onreflexio_tanulsag_jeloltek_egyszer(db):
    from datetime import datetime, timezone

    db.add(LaraKerdes(tipus="papir", allapot="megvalaszolt", kulcs="refl|1", partner_nev="Reflexió Kft.", kerdes="Miért nincs TIG?",
                      valasz_tipus="magyarazat", valasz_szoveg="Havidíjas partner.", megvalaszolva_at=datetime.now(timezone.utc)))
    db.flush()
    llm.teszt_adapter(lambda *_: {"osszefoglalo": "A havidíjas partnereknél tévedtem.",
                                  "tanulsagok": [{"hatokor": "tig", "tanulsag": "Havidíjasnál nem kell eseti TIG.",
                                                  "mit_csinalok_maskepp": "Előbb keretszerződést keresek."}],
                                  "gyenge_pontok": ["havidíjas partnerek"]})
    r = gemini_tanulas.onreflexio(db)
    assert r["allapot"] == "kesz" and r["uj_tanulsag"] == 1
    m = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("gemini:tanulsag:%")).order_by(MemoryChunk.id.desc())).first()
    assert not m.ervenyes and "Előbb keretszerződést keresek." in m.tartalom
    run = db.scalar(select(LearningRun).where(LearningRun.trigger == "gemini_tanulas:reflexio").order_by(LearningRun.id.desc()))
    assert run.osszefoglalo["gyenge_pontok"] == ["havidíjas partnerek"]
    assert gemini_tanulas.onreflexio(db)["allapot"] == "valtozatlan"


def test_gemini_allapot_kozos_kulcs_es_kapcsolat(db):
    a = gemini_tanulas.allapot(db)
    assert a["kozos_az_asszisztenssel"] is True and a["modell"]
    assert {f["kulcs"] for f in a["funkciok"]} >= {"nyomozas", "megoldas", "gemini_tanulas", "szamla_elemzes"}
    from app.core.config import settings

    # A kulcs értéke sosem kerül a válaszba, csak az, hogy be van-e állítva.
    assert isinstance(a["kulcs_beallitva"], bool)
    assert not settings.gemini_api_key or settings.gemini_api_key not in json.dumps(a)
    llm.teszt_adapter(lambda *_: {"ok": True})
    assert gemini_tanulas.kapcsolat_teszt()["ok"] is True
