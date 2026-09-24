"""Lara — tapasztalás (tények a teljes történetből + Gemini-állítások adaton
ellenőrizve) és a mai dátum a modellhívásokban.

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback.
Valódi modellhívás nincs (hamis adapter)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import llm, tapasztalas
from app.admin_agent.memory import partner_kulcs
from app.admin_agent.tudashalo import tudashalo
from app.models.admin_agent import MemoryChunk, SourceEvent
from app.models.finance import Expense
from app.models.project_code import ProjectCode

PARTNER = "Tapasztalat Teszt Kft."


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
        llm.teszt_adapter(None)
        sess.rollback()
        sess.close()


def _adat(db, n_kod: int = 4, n_mas: int = 1) -> ProjectCode:
    pc = ProjectCode(projektkod="TAPASZT-1", megrendelo_neve="Tapasztalat Megrendelő Zrt.")
    masik = ProjectCode(projektkod="TAPASZT-2")
    db.add_all([pc, masik])
    db.flush()
    db.add_all([Expense(megnevezes=PARTNER, netto=100_000 + i, brutto=127_000, kesz=True, tipus="Alvállalkozó",
                        project_code_id=pc.id) for i in range(n_kod)])
    db.add_all([Expense(megnevezes=PARTNER, netto=90_000, brutto=114_300, kesz=True, tipus="Alvállalkozó",
                        project_code_id=masik.id) for _ in range(n_mas)])
    db.add(Expense(megnevezes=PARTNER, netto=1, brutto=1, kesz=False))  # nyitott: nem tény
    db.flush()
    return pc


def _esemeny(db) -> SourceEvent:
    return db.scalar(select(SourceEvent).where(SourceEvent.forras == tapasztalas.FORRAS,
                                               SourceEvent.forras_azonosito == f"partner:{partner_kulcs(PARTNER)}"))


def test_mai_datum_budapesti_es_minden_hivasban():
    assert llm.mai_datum(datetime(2026, 9, 24, 22, 30, tzinfo=timezone.utc)).startswith("MAI DÁTUM: 2026-09-25 (péntek)")
    assert llm.mai_datum(datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)).startswith("MAI DÁTUM: 2026-09-24 (csütörtök)")
    kapott = []
    llm.teszt_adapter(lambda rendszer, *_: kapott.append(rendszer) or {"ok": True})
    try:
        llm.strukturalt_hivas("x", {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]})
    finally:
        llm.teszt_adapter(None)
    assert "MAI DÁTUM:" in kapott[0] and kapott[0].count("MAI DÁTUM:") == 1


def test_tenyek_a_teljes_tortenetbol_idempotensen(db):
    pc = _adat(db)
    stat = tapasztalas.teny_gyujtes(db)
    assert stat.get("uj_partner", 0) >= 1
    se = _esemeny(db)
    assert se is not None and se.metaadat["ossz"] == 5  # a nyitott kiadás nem számít
    tenyek = {(t["fajta"], t["ertek"]): t for t in se.metaadat["tenyek"]}
    assert tenyek[("forras", "kiadas")]["n"] == 5
    assert tenyek[("projektkod", str(pc.id))]["n"] == 4 and tenyek[("projektkod", str(pc.id))]["ossz"] == 5
    assert ("projektkod", "x") not in tenyek and all(t["n"] >= 2 for t in tenyek.values())  # 1 eset nem tapasztalat
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"tapasztalas:partner:{partner_kulcs(PARTNER)}"))
    assert m.ervenyes and m.minosites == tapasztalas.TENY and "TAPASZT-1 4/5" in m.tartalom
    assert tapasztalas.teny_gyujtes(db).get("valtozatlan", 0) >= 1 and _esemeny(db).id == se.id


def test_gemini_allitas_csak_adat_igazolasaval_es_ujraellenorzes(db):
    _adat(db)
    minden = tapasztalas.rekordok(db)
    tapasztalas.teny_gyujtes(db, minden)
    halo_elotte = tudashalo(db)
    kerdezett = []

    def adapter(rendszer, szoveg, _sema):
        kerdezett.append(szoveg)
        return {"allitasok": [
            {"tipus": "projektkod", "ertek": "TAPASZT-1", "szoveg": "A számláit a TAPASZT-1 kódra rögzítjük."},
            {"tipus": "osszeg_sav", "ertek": "", "also": 1_000_000, "felso": 2_000_000, "szoveg": "Milliós számlák."},
            {"tipus": "tipus", "ertek": "alvállalkozó", "szoveg": "Alvállalkozóként számláz."},
        ]}

    llm.teszt_adapter(adapter)
    # Csak a teszt-partnert kérdezze: a többi (valós) partner már „vizsgált".
    for se in db.scalars(select(SourceEvent).where(SourceEvent.forras == tapasztalas.FORRAS)).all():
        if se.metaadat.get("partner") != partner_kulcs(PARTNER):
            se.metaadat = {**se.metaadat, "hipotezis_lenyomat": se.forras_verzio}
    r = tapasztalas.hipotezis_kor(db, 1, minden)
    assert len(kerdezett) == 1 and PARTNER in kerdezett[0]
    assert r["igazolt"] == 2 and r["cafolt"] == 1  # 4/5 kód (80%) és 5/5 típus igaz; a milliós sáv nem
    se = _esemeny(db)
    assert {a["tipus"] for a in se.metaadat["igazolt"]} == {"projektkod", "tipus"}
    assert se.metaadat["cafolt"][-1]["tipus"] == "osszeg_sav"
    igazolt = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("tapasztalas:allitas:%"),
                                                   MemoryChunk.minosites == tapasztalas.IGAZOLT)).all()
    assert any("4/5 rögzített eset igazolja (80%)" in m.tartalom for m in igazolt)
    # Ugyanarra az adatra nem kérdez újra.
    assert tapasztalas.hipotezis_kor(db, 1, minden).get("partner", 0) == 0

    # A tudásháló a tapasztalattal erősebb, és a kapcsolat „tapasztalt".
    halo = tudashalo(db)
    pid = f"partner:{partner_kulcs(PARTNER)}"
    elek = [e for e in halo["elek"] if pid in (e["a"], e["b"])]
    assert elek and all(e["tapasztalat"] > 0 for e in elek)
    assert max(e["bizonyossag"] for e in elek) >= 0.6
    # Az adaton igazolt állítások növelik a partner kapcsolatainak bizonyosságát.
    elotte = {(e["a"], e["b"]): e["bizonyossag"] for e in halo_elotte["elek"] if pid in (e["a"], e["b"])}
    assert elotte and any(e["bizonyossag"] > elotte.get((e["a"], e["b"]), 0) for e in elek)

    # Új adat: a kód már csak 4/8 → az állítás visszavonva, a típus marad.
    masik = db.scalar(select(ProjectCode).where(ProjectCode.projektkod == "TAPASZT-2"))
    db.add_all([Expense(megnevezes=PARTNER, netto=90_000, brutto=1, kesz=True, tipus="Alvállalkozó",
                        project_code_id=masik.id) for _ in range(3)])
    db.flush()
    stat = tapasztalas.teny_gyujtes(db)
    assert stat.get("visszavont", 0) >= 1
    se = _esemeny(db)
    assert [a["tipus"] for a in se.metaadat["igazolt"]] == ["tipus"]
    kod_allitas = next(m for m in db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("tapasztalas:allitas:%"))).all()
                       if "TAPASZT-1" in m.tartalom)
    assert not kod_allitas.ervenyes and kod_allitas.minosites == tapasztalas.CAFOLT


def test_modellhiba_eseten_a_tenyek_megmaradnak(db):
    _adat(db)
    minden = tapasztalas.rekordok(db)
    tapasztalas.teny_gyujtes(db, minden)

    def hibas(*_):
        raise llm.ModellHiba("429")

    llm.teszt_adapter(hibas)
    r = tapasztalas.hipotezis_kor(db, 3, minden)
    assert r["hiba"] == 1 and _esemeny(db).metaadat.get("igazolt") in (None, [])


def test_api_tapasztalas_allapot(db):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    fej = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
    r = TestClient(app).get("/api/v1/admin-agent/gemini", headers=fej)
    assert r.status_code == 200 and "tapasztalas" in r.json()
    assert set(r.json()["tapasztalas"]) >= {"partnerek", "tenyek", "igazolt_allitasok", "gemini_talalati_arany"}
    assert TestClient(app).post("/api/v1/admin-agent/experience").status_code == 401
