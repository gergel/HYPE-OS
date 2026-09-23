"""Lara — önellenőrző, folyamatos tanulás (kérdés → válasz → tudás).

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
VALÓDI MODELLHÍVÁS NINCS.

Fedi a teljes kört: Lara a rögzített munkára „vakon" jósol a jelenlegi
tudásával; ahol eltér és nem érti, KÉRDEZ (partnerenként egy kérdés, ismételt
futásnál nincs duplikátum); a „mindig így" válaszból élesített szabály lesz, és
a következő önellenőrzésen már eltalálja (nő a találati arány); a magyarázat
tudássá válik, és az éles elemzés is használja; a „hibás rögzítés" nem tanít;
a vak jóslat nem használja az adott számla saját tanulságát.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import llm


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


@pytest.fixture(autouse=True)
def _modell_nelkul(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    llm.teszt_adapter(None)


def _kod(db, kod):
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod=kod)
    db.add(pc)
    db.flush()
    return pc


def _rogzitett(db, partner, szamlaszam, *, erkezteto, vegso, pc=None):
    from app.models.bejovo_szamla import ALLAPOT_JOVAHAGYVA, BejovoSzamla

    b = BejovoSzamla(
        allapot=ALLAPOT_JOVAHAGYVA, kibocsato_nev=partner, szamlaszam=szamlaszam, netto=10000, brutto=12700,
        penznem="HUF", javaslat={"tipus": erkezteto}, cel_tipus=vegso, cel_project_code_id=pc.id if pc else None,
        jovahagyva_at=datetime.now(timezone.utc),
    )
    db.add(b)
    db.flush()
    return b


def _kerdes(db, kulcs):
    from app.models.admin_agent import LaraKerdes

    return db.scalars(select(LaraKerdes).where(LaraKerdes.kulcs == kulcs)).all()


def test_nem_erti_kerdez_valasz_utan_eltalalja(db):
    from app.admin_agent.onellenorzes import Tudas, onellenorzes, valaszol

    pc = _kod(db, "ONELL-TESZT-1")
    for i in range(2):
        _rogzitett(db, "Kérdező Partner EV", f"KP-{i}", erkezteto="mukodesi", vegso="kiadas_uj", pc=pc)

    elso = onellenorzes(db)
    db.flush()
    kerdesek = _kerdes(db, "kerdezo partner|kiadas_uj")
    assert len(kerdesek) == 1  # a két eset EGY kérdésben
    k = kerdesek[0]
    assert k.allapot == "nyitott" and len(k.kontextus["esetek"]) == 2
    assert "ezt javasoltam volna" in k.kerdes and "Nála mindig így kell?" in k.kerdes

    # Ismételt futás: nincs duplikált kérdés.
    onellenorzes(db)
    db.flush()
    assert len(_kerdes(db, "kerdezo partner|kiadas_uj")) == 1

    # Válasz: „mindig így" → élesített, partnerre szabott szabály.
    e = valaszol(db, k, valasz_tipus="mindig", magyarazat="Ő a forgatásokon dolgozik.", user_id=2, elesithet=True)
    assert e["szabaly_allapot"] == "active"
    t = Tudas(db).cel("kerdezo partner")
    assert t["tipus"] == "kiadas_uj" and t["kod_idk"] == [pc.id] and t["fajta"] == "szabaly"

    # A következő önellenőrzésen már eltalálja → nő a találati arány.
    masodik = onellenorzes(db)
    assert masodik["egyezik"] - elso["egyezik"] == 2
    assert (masodik["talalati_arany"] or 0) > (elso["talalati_arany"] or 0)


def test_szabaly_jeloltkent_ha_nincs_elesitesi_jog(db):
    from app.admin_agent.onellenorzes import onellenorzes, valaszol

    _rogzitett(db, "Jelölt Partner Kft.", "JP-1", erkezteto=None, vegso="mukodesi")
    onellenorzes(db)
    db.flush()
    k = _kerdes(db, "jelolt partner|mukodesi")[0]
    assert "Nem tudtam, hová kerülnek" in k.kerdes
    e = valaszol(db, k, valasz_tipus="mindig", magyarazat=None, user_id=2, elesithet=False)
    assert e["szabaly_allapot"] == "pending"  # a Tudástárban élesíthető, értékelés után


def test_magyarazat_tudassa_valik_es_az_eles_elemzes_hasznalja(db):
    from app.admin_agent.onellenorzes import Tudas, ValaszHiba, onellenorzes, valaszol
    from app.admin_agent.pipeline_szamla import arnyek_elemzes
    from app.models.admin_agent import ActionProposal, MemoryChunk
    from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, BejovoSzamla

    for i in range(2):
        _rogzitett(db, "Magyarázó Bt.", f"MB-{i}", erkezteto=None, vegso="mukodesi")
    onellenorzes(db)
    db.flush()
    k = _kerdes(db, "magyarazo|mukodesi")[0]
    with pytest.raises(ValaszHiba):
        valaszol(db, k, valasz_tipus="magyarazat", magyarazat="  ", user_id=2, elesithet=False)
    e = valaszol(db, k, valasz_tipus="magyarazat", magyarazat="Irodai takarítás, nem projektköltség.",
                 user_id=2, elesithet=False)
    m = db.get(MemoryChunk, e["pelda_id"])
    assert m.ervenyes is True and "Irodai takarítás" in m.tartalom
    assert Tudas(db).cel("magyarazo")["fajta"] == "peldak"

    # Új számla ugyanettől a partnertől: az éles elemzés a tanult tudásból tölt.
    b = BejovoSzamla(allapot=ALLAPOT_ELLENORZENDO, kibocsato_nev="Magyarázó Bt.", szamlaszam="MB-UJ",
                     netto=1000, brutto=1270, penznem="HUF", javaslat={})
    db.add(b)
    db.flush()
    t = arnyek_elemzes(db, b)
    db.flush()
    p = db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).first()
    assert p.payload["cel_tipus"] == "mukodesi"
    assert p.ellenorzesek["szabaly"]["fajta"] == "peldak"
    assert t.uncertainty == 0.45


def test_hibas_rogzites_nem_tanit_es_vak_josolat(db):
    from app.admin_agent.onellenorzes import Tudas, onellenorzes, valaszol
    from app.models.admin_agent import PlaybookRule

    _rogzitett(db, "Hibás Rögzítés Kft.", "HR-1", erkezteto="mukodesi", vegso="kiadas_uj")
    onellenorzes(db)
    db.flush()
    k = _kerdes(db, "hibas rogzites|kiadas_uj")[0]
    e = valaszol(db, k, valasz_tipus="hibas", magyarazat=None, user_id=2, elesithet=True)
    assert e["szabaly_id"] is None and e["pelda_id"] is None
    assert Tudas(db).cel("hibas rogzites") is None
    assert not [r for r in db.scalars(select(PlaybookRule)).all() if (r.feltetelek or {}).get("partner") == "hibas rogzites"]
    # A megválaszolt esetre nem kérdez újra.
    ujra = onellenorzes(db)
    assert ujra["megmagyarazva"] >= 1
    assert len(_kerdes(db, "hibas rogzites|kiadas_uj")) == 1


def test_vak_josolat_nem_puskaz(db):
    """Egyetlen jóváhagyott eset saját magát nem „tanítja": kivéve önmagát nincs tudás."""
    from app.admin_agent.onellenorzes import Tudas
    from app.admin_agent.visszajatszas import visszajatszas
    from app.models.admin_agent import MemoryChunk

    b1 = _rogzitett(db, "Puska Kft.", "PK-1", erkezteto=None, vegso="mukodesi")
    b2 = _rogzitett(db, "Puska Kft.", "PK-2", erkezteto=None, vegso="mukodesi")
    visszajatszas(db)
    for m in db.scalars(select(MemoryChunk).where(MemoryChunk.forras.in_([f"visszajatszas:bejovo:{b1.id}", f"visszajatszas:bejovo:{b2.id}"]))).all():
        m.ervenyes = True
    db.flush()
    t = Tudas(db)
    assert t.cel("puska") is not None  # két jóváhagyott eset → tud róla
    assert t.cel("puska", kiveve=b1.id) is None  # önmagát kivéve csak egy marad → nem jósol


def test_api_valasz_validalas_es_futasok():
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
        r = c.post("/api/v1/admin-agent/questions/999999999/answer", headers=h, json={"valasz_tipus": "mindig"})
    except OperationalError:
        pytest.skip("Postgres nem elérhető.")
    assert r.status_code == 404
    r = c.get("/api/v1/admin-agent/self-check/runs", headers=h)
    assert r.status_code == 200 and "elemek" in r.json()
    r = c.get("/api/v1/admin-agent/questions", headers=h)
    assert r.status_code == 200
