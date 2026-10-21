"""Lara: a feladat ellenőrzésénél elég egy ÖSSZEFOGLALÓ MAGYARÁZAT is.

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
A route-függvényt közvetlenül hívjuk (a commit helyett flush), hogy a teszt ne
hagyjon nyomot az adatbázisban.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError


@pytest.fixture()
def db(monkeypatch):
    from app.core.database import SessionLocal

    try:
        sess = SessionLocal()
        sess.execute(select(1))
    except OperationalError:
        pytest.skip("Postgres nem elérhető — integrációs teszt kihagyva.")
    monkeypatch.setattr(sess, "commit", sess.flush)
    try:
        yield sess
    finally:
        sess.rollback()
        sess.close()


def _feladat(db):
    from app.models.admin_agent import ActionProposal, AdminTask

    t = AdminTask(tipus="szamla", cim="Számla: Magyarázat Teszt Kft. — MT-1", allapot="proposal_ready",
                  partner_nev="Magyarázat Teszt Kft.", trust_level="L0")
    db.add(t)
    db.flush()
    p = ActionProposal(task_id=t.id, eszkoz="szamla.jovahagyas", payload={"cel_tipus": "mukodesi", "netto": 12000},
                       payload_hash="x" * 64, allapot="ready", kockazat="R2")
    db.add(p)
    db.flush()
    return t, p


def test_csak_magyarazat_azonnal_tudassa_valik(db):
    from app.admin_agent.memory import kapcsolodo_tudas
    from app.api.routes.admin_agent import CorrectionIn, task_correction
    from app.models.admin_agent import Correction, MemoryChunk

    t, p = _feladat(db)
    e = task_correction(
        t.id,
        CorrectionIn(proposal_id=p.id, magyarazat="Ez a DEMO-X forgatás technikai bérlése, annak a kódjára kellett volna."),
        db,
        SimpleNamespace(id=2),
    )
    c = db.get(Correction, e["correction_id"])
    assert c.tipus == "magyarazat" and c.feldolgozas_allapot == "feldolgozva" and not c.mezo_diff
    m = db.get(MemoryChunk, e["pelda_id"])
    assert m.ervenyes and m.hatokor == "szamla"
    assert "Magyarázat Teszt Kft." in m.tartalom and "cel_tipus: mukodesi" in m.tartalom
    assert "DEMO-X forgatás technikai bérlése" in m.tartalom
    # A számla-elemzés a partner szerint előveszi.
    talalat = kapcsolodo_tudas(db, hatokor="szamla", partner="Magyarázat Teszt Kft.")["hasonlo_esetek"]
    assert any("DEMO-X" in x["tartalom"] for x in talalat)
    assert db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"correction:{c.id}")) is not None


def test_mezos_javitas_valtozatlan_es_ures_kuldes_hiba(db):
    from app.api.routes.admin_agent import CorrectionIn, task_correction
    from app.models.admin_agent import Correction

    t, p = _feladat(db)
    with pytest.raises(HTTPException) as hiba:
        task_correction(t.id, CorrectionIn(proposal_id=p.id, magyarazat="   "), db, SimpleNamespace(id=2))
    assert hiba.value.status_code == 400

    e = task_correction(
        t.id,
        CorrectionIn(proposal_id=p.id, javitott={"cel_tipus": "kiadas_uj"}, tipus="tenyszeru_hiba", magyarazat="rossz cél"),
        db,
        SimpleNamespace(id=2),
    )
    c = db.get(Correction, e["correction_id"])
    assert e["pelda_id"] is None and c.feldolgozas_allapot == "uj" and "cel_tipus" in c.mezo_diff
