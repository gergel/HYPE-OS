"""Admin-Ágens — F fázis (tanulás, eval, retrieval, kiadás) tesztjei.

Fedi a 13., 14., 15., 22. forgatókönyvet: emberi javításból JELÖLT (nem csendben
aktív) szabály; sikertelen/hiányos eval megakadályozza az aktiválást; visszavont
memória nem kerül vissza; a distill idempotens (nincs dupla feldolgozás).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.evals import run_eval, safety_esetek_magveto
from app.admin_agent.learning import distill
from app.admin_agent.memory import retrieve
from app.models.admin_agent import (
    AdminTask,
    Correction,
    EvalCase,
    LearningRun,
    MemoryChunk,
    PlaybookRule,
)


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


def _task(db, tipus="szamla") -> AdminTask:
    t = AdminTask(tipus=tipus, cim="tanuló teszt", allapot="completed", trust_level="L0")
    db.add(t)
    db.flush()
    return t


def _korrekcio(db, task_id, mezo="cel_tipus", tipus="tenyszeru_hiba") -> Correction:
    c = Correction(
        task_id=task_id,
        eredeti={mezo: "a"},
        javitott={mezo: "b"},
        mezo_diff={mezo: {"elozo": "a", "uj": "b"}},
        tipus=tipus,
        feldolgozas_allapot="uj",
    )
    db.add(c)
    db.flush()
    return c


def test_distill_kuszob_es_idempotencia(db):
    """13/22: két hasonló tényszerű javításból EGY szabály-JELÖLT (pending, nem
    aktív); a distill idempotens (újrafuttatva nem dolgoz fel újra)."""
    t = _task(db)
    c1 = _korrekcio(db, t.id)
    c2 = _korrekcio(db, t.id)
    db.flush()
    ids = [t.id, c1.id, c2.id]
    try:
        lr = distill(db, trigger="manual")
        db.commit()
        assert lr.feldolgozott_korrekciok >= 2
        # A frissen keletkezett szabály-jelölt PENDING (soha nem auto-aktív).
        jelolt = db.scalars(
            select(PlaybookRule).where(PlaybookRule.forras_esetek.isnot(None), PlaybookRule.hatokor == "szamla")
        ).all()
        ehhez = [r for r in jelolt if set((r.forras_esetek or {}).get("correction_ids", [])) & {c1.id, c2.id}]
        assert len(ehhez) == 1
        assert ehhez[0].allapot == "pending"
        rule_id = ehhez[0].id
        # A példa-jelöltek NEM érvényesek (nem használhatók éles döntésben).
        peldak = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.in_([f"correction:{c1.id}", f"correction:{c2.id}"]))).all()
        assert peldak and all(m.ervenyes is False for m in peldak)
        # Idempotencia: újra → 0 új feldolgozott.
        lr2 = distill(db, trigger="manual")
        db.commit()
        assert lr2.feldolgozott_korrekciok == 0
    finally:
        db.query(PlaybookRule).filter(PlaybookRule.hatokor == "szamla", PlaybookRule.forras_esetek.isnot(None)).delete(synchronize_session=False)
        db.query(MemoryChunk).filter(MemoryChunk.forras.in_([f"correction:{c1.id}", f"correction:{c2.id}"])).delete(synchronize_session=False)
        db.query(Correction).filter(Correction.task_id == t.id).delete(synchronize_session=False)
        db.query(LearningRun).filter(LearningRun.id.in_([lr.id, lr2.id])).delete(synchronize_session=False)
        db.query(AdminTask).filter(AdminTask.id == t.id).delete(synchronize_session=False)
        db.commit()


def test_egyetlen_javitasbol_nincs_szabaly(db):
    """Egy javításból NEM lesz szabály-jelölt (küszöb alatt)."""
    t = _task(db)
    c = _korrekcio(db, t.id)
    db.flush()
    try:
        lr = distill(db, trigger="manual")
        db.commit()
        assert lr.uj_szabaly_jeloltek == 0
    finally:
        db.query(MemoryChunk).filter(MemoryChunk.forras == f"correction:{c.id}").delete(synchronize_session=False)
        db.query(Correction).filter(Correction.task_id == t.id).delete(synchronize_session=False)
        db.query(LearningRun).filter(LearningRun.id == lr.id).delete(synchronize_session=False)
        db.query(AdminTask).filter(AdminTask.id == t.id).delete(synchronize_session=False)
        db.commit()


def test_eval_biztonsagi_invariansok_atmennek(db):
    """14: a beépített biztonsági eval-esetek átmennek (a policy engine helyes),
    kritikus hiba nélkül."""
    safety_esetek_magveto(db)
    db.commit()
    run = run_eval(db)
    db.commit()
    try:
        assert run.osszes >= 7
        assert run.kritikus_hiba == 0
        assert run.atment is True
    finally:
        from app.models.admin_agent import EvalRun

        db.query(EvalRun).filter(EvalRun.id == run.id).delete(synchronize_session=False)
        db.commit()


def test_retrieval_csak_aktiv_es_ervenyes(db):
    """15: a visszakeresés csak AKTÍV szabályt és ÉRVÉNYES, nem visszavont,
    jóváhagyott példát ad; a pending/visszavont kimarad."""
    aktiv = PlaybookRule(hatokor="reteszt", cim="aktív", tartalom="x", allapot="active", verzio=1)
    pending = PlaybookRule(hatokor="reteszt", cim="jelölt", tartalom="y", allapot="pending", verzio=1)
    jo = MemoryChunk(hatokor="reteszt", tartalom="jó példa", tanulasi_halmaz="jovahagyott", ervenyes=True)
    visszavont = MemoryChunk(hatokor="reteszt", tartalom="visszavont", tanulasi_halmaz="jovahagyott", ervenyes=True, visszavont=True)
    holdout = MemoryChunk(hatokor="reteszt", tartalom="holdout", tanulasi_halmaz="holdout", ervenyes=True)
    db.add_all([aktiv, pending, jo, visszavont, holdout])
    db.commit()
    try:
        r = retrieve(db, hatokor="reteszt")
        cimek = {s["cim"] for s in r["szabalyok"]}
        assert "aktív" in cimek and "jelölt" not in cimek
        tartalmak = {m["tartalom"] for m in r["peldak"]}
        assert "jó példa" in tartalmak
        assert "visszavont" not in tartalmak and "holdout" not in tartalmak
    finally:
        db.query(PlaybookRule).filter(PlaybookRule.hatokor == "reteszt").delete(synchronize_session=False)
        db.query(MemoryChunk).filter(MemoryChunk.hatokor == "reteszt").delete(synchronize_session=False)
        db.commit()
