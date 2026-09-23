"""HYRON — modelladapter és a modell-alapú számla-átnézés tesztjei.

VALÓDI MODELLHÍVÁS NINCS: izolált hamis adapter (`llm.teszt_adapter`) adja a
válaszokat, hibát is szimulálva. A valódi Gemini-teszt külön, explicit
kulccsal futtatandó (lásd docs/admin-agent/acceptance-checklist.md).

Fedi (master prompt 9./16.): séma-ellenőrzés + korlátos újrapróba; 429/timeout
→ kontrollált hiba; a modell nem talál ki projektkódot; eltérés → ember; az
összeget a modell nem írhatja át; modell nélkül a determinista út marad.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import llm

SEMA = {
    "type": "object",
    "required": ["a", "b"],
    "properties": {"a": {"type": "string"}, "b": {"type": "number"}},
}


@pytest.fixture(autouse=True)
def _adapter_vissza():
    yield
    llm.teszt_adapter(None)


def test_adapter_ervenyes_valasz():
    llm.teszt_adapter(lambda r, f, s: {"a": "x", "b": 1})
    v = llm.strukturalt_hivas("kérdés", SEMA)
    assert v.adat == {"a": "x", "b": 1} and v.probalkozas == 1


def test_adapter_hibas_json_utan_javito_ujraproba():
    hivasok = []

    def fake(r, f, s):
        hivasok.append(f)
        return {"a": "x"} if len(hivasok) == 1 else {"a": "x", "b": 2}

    llm.teszt_adapter(fake)
    v = llm.strukturalt_hivas("kérdés", SEMA)
    assert v.probalkozas == 2
    assert "ÉRVÉNYTELEN" in hivasok[1]  # a második hívás javító utasítást kapott


def test_adapter_tartosan_hibas_valasz_kontrollalt_hiba():
    llm.teszt_adapter(lambda r, f, s: {"a": 5})
    with pytest.raises(llm.ModellHiba):
        llm.strukturalt_hivas("kérdés", SEMA)


def test_adapter_429_timeout_kontrollalt_hiba():
    def fake(r, f, s):
        raise TimeoutError("429 RESOURCE_EXHAUSTED")

    llm.teszt_adapter(fake)
    with pytest.raises(llm.ModellHiba):
        llm.strukturalt_hivas("kérdés", SEMA)


def test_nincs_kulcs_beallitas_szukseges(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    llm.teszt_adapter(None)
    with pytest.raises(llm.ModellNincsBeallitva):
        llm.strukturalt_hivas("kérdés", SEMA)


# ── A modell-alapú számla-átnézés (Postgres, rollback) ──────────────────────


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


def _szamla(db, **kw):
    from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, BejovoSzamla

    alap = dict(allapot=ALLAPOT_ELLENORZENDO, kibocsato_nev="LLM Teszt Kft.", szamlaszam="LLM-1",
                netto=10000, brutto=12700, penznem="HUF")
    alap.update(kw)
    b = BejovoSzamla(**alap)
    db.add(b)
    db.flush()
    return b


def _projektkod(db, kod):
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod=kod)
    db.add(pc)
    db.flush()
    return pc


def _javaslat(db, task):
    from app.models.admin_agent import ActionProposal

    return db.scalars(select(ActionProposal).where(ActionProposal.task_id == task.id)).first()


def _valasz(**kw):
    alap = {"osszefoglalo": "Átnézve.", "cel_tipus": "", "projektkod": "", "indoklas": "teszt",
            "bizonytalansag": 0.2, "hianyzo_adatok": []}
    alap.update(kw)
    return lambda r, f, s: alap


def test_modell_kitolti_ures_celt_letezo_projektkoddal(db):
    from app.admin_agent.pipeline_szamla import arnyek_elemzes

    pc = _projektkod(db, "LLMTESZT-001")
    b = _szamla(db)
    llm.teszt_adapter(_valasz(cel_tipus="kiadas_uj", projektkod="LLMTESZT-001"))
    t = arnyek_elemzes(db, b)
    db.flush()
    p = _javaslat(db, t)
    assert p.payload["cel_tipus"] == "kiadas_uj"
    assert p.payload["cel_project_code_id"] == pc.id
    # Az ÖSSZEG a dokumentumból jön, a modell nem írhatja át.
    assert p.payload["netto"] == 10000.0 and p.payload["brutto"] == 12700.0
    # Nincs alátámasztó jóváhagyott eset → legalább közepes bizonytalanság.
    assert t.uncertainty is not None and t.uncertainty >= 0.6
    assert p.ellenorzesek["modell"]["hasznalt"] is True


def test_modell_kitalalt_projektkodja_elutasitva(db):
    from app.admin_agent.pipeline_szamla import arnyek_elemzes

    b = _szamla(db, cel_tipus="kiadas_uj")
    llm.teszt_adapter(_valasz(cel_tipus="kiadas_uj", projektkod="NEMLETEZO-999"))
    t = arnyek_elemzes(db, b)
    db.flush()
    p = _javaslat(db, t)
    assert p.payload["cel_project_code_id"] is None
    assert any("nem létező projektkód" in f for f in p.ellenorzesek["modell"]["figyelmeztetesek"])


def test_eltero_projektkod_konfliktus_emberhez(db):
    from app.admin_agent.pipeline_szamla import arnyek_elemzes

    a = _projektkod(db, "LLMTESZT-A")
    _projektkod(db, "LLMTESZT-B")
    b = _szamla(db, cel_tipus="kiadas_uj", cel_project_code_id=a.id)
    llm.teszt_adapter(_valasz(cel_tipus="kiadas_uj", projektkod="LLMTESZT-B"))
    t = arnyek_elemzes(db, b)
    db.flush()
    p = _javaslat(db, t)
    assert p.payload["cel_project_code_id"] == a.id  # az érkeztetőé marad
    assert t.allapot == "needs_info" and t.uncertainty == 1.0
    assert p.allapot == "draft"  # nem hajtható végre, jóváhagyás mellett sem
    assert "eltérés" in (t.blokkolo_ok or "").lower()


def test_modellhiba_eseten_determinista_ut(db):
    from app.admin_agent.pipeline_szamla import arnyek_elemzes

    def hibas(r, f, s):
        raise TimeoutError("timeout")

    b = _szamla(db, cel_tipus="mukodesi")
    llm.teszt_adapter(hibas)
    t = arnyek_elemzes(db, b)
    db.flush()
    p = _javaslat(db, t)
    assert p.payload["cel_tipus"] == "mukodesi"
    assert p.ellenorzesek["modell"]["allapot"] == "hiba"
    assert t.uncertainty is None  # ismeretlen → emberi ellenőrzés, nem hamis nulla
