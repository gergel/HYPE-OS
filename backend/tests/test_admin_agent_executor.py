"""Admin-Ágens — végrehajtó guard-lánc elfogadási tesztjei (master prompt 16.).

Postgres-integráció (JSONB), DB nélkül self-skip. A biztonságos alapállásban
(modul KI, mellékhatás TILT) a végrehajtás mindig blokkolt: SEMMILYEN üzleti
rekord nem jön létre. A tesztek a guard-láncot bizonyítják:

- 4/10: L0 / modul ki / vészleállítás → a következő mellékhatás blokkolt.
- 5: elavult (consumed) jóváhagyással nincs végrehajtás.
- 6: a jóváhagyás a javaslat-hash-hez kötött; eltérő hash → blokkolt.
- 7: dupla hívásból EGY végrehajtási rekord (idempotencia).
"""

from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.enums import ApprovalState, ProposalState, RiskClass, TaskType
from app.admin_agent.executor import execute_approved
from app.models.admin_agent import (
    ActionExecution,
    ActionProposal,
    ActionTrace,
    AdminTask,
    Approval,
)
from app.models.employee import Employee
from app.models.finance import Expense


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


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _beallitas(db, *, module: bool, side: bool, kill: bool = False) -> None:
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.module_enabled = module
    s.side_effects_enabled = side
    s.kill_switch = kill
    db.flush()


def _feladat_javaslat_jovahagyas(db, *, payload_hash_override: str | None = None):
    """Létrehoz egy R2 számla-feladatot, egy READY javaslatot és egy APPROVED
    jóváhagyást. A payload olyan, hogy a valós szolgáltatás EL NEM ér (a
    végrehajtás a guardokon fennakad, mielőtt a tool hívódna)."""
    payload = {"cel_tipus": "mukodesi", "brutto": 1270.0, "netto": 1000.0, "penznem": "HUF"}
    ph = _hash(payload)
    t = AdminTask(
        tipus=TaskType.SZAMLA.value,
        altipus="mukodesi",
        cim="Exec teszt",
        allapot="awaiting_approval",
        trust_level="L0",
        kockazat="R2",
        forras_referenciak={"bejovo_szamla_id": -1},  # szándékosan nem létező
    )
    db.add(t)
    db.flush()
    p = ActionProposal(
        task_id=t.id,
        eszkoz="szamla_erkeztetes.jovahagy",
        payload=payload,
        payload_hash=ph,
        kockazat=RiskClass.R2.value,
        allapot=ProposalState.READY.value,
    )
    db.add(p)
    db.flush()
    a = Approval(
        proposal_id=p.id,
        payload_hash=payload_hash_override or ph,
        allapot=ApprovalState.APPROVED.value,
    )
    db.add(a)
    db.flush()
    return t, p, a


def _takarits(db, t: AdminTask) -> None:
    pids = [p.id for p in db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).all()]
    if pids:
        db.query(ActionExecution).filter(ActionExecution.proposal_id.in_(pids)).delete(synchronize_session=False)
        db.query(Approval).filter(Approval.proposal_id.in_(pids)).delete(synchronize_session=False)
    db.query(ActionTrace).filter(ActionTrace.task_id == t.id).delete(synchronize_session=False)
    db.query(ActionProposal).filter(ActionProposal.task_id == t.id).delete(synchronize_session=False)
    db.query(AdminTask).filter(AdminTask.id == t.id).delete(synchronize_session=False)
    db.commit()


def _approver(db) -> Employee:
    emp = db.scalars(select(Employee).limit(1)).first()
    if emp is None:
        pytest.skip("Nincs Employee a teszthez.")
    return emp


def test_alapallas_blokkol_es_nincs_expense(db):
    """4/10: modul KI + mellékhatás TILT → a végrehajtás blokkolt, 0 Expense."""
    _beallitas(db, module=False, side=False)
    exp_elott = db.query(Expense).count()
    t, p, a = _feladat_javaslat_jovahagyas(db)
    try:
        ex = execute_approved(db, a, approver=_approver(db))
        db.commit()
        assert ex.allapot == "failed"  # blokkolt (nem sikeres, nem futott a tool)
        assert "blokk_ok" in (ex.eredmeny or {})
        assert db.query(Expense).count() == exp_elott  # SEMMI üzleti mellékhatás
    finally:
        _takarits(db, t)


def test_veszleallitas_blokkol(db):
    """10: modul+mellékhatás BE, de vészleállítás → blokkolt."""
    _beallitas(db, module=True, side=True, kill=True)
    t, p, a = _feladat_javaslat_jovahagyas(db)
    try:
        ex = execute_approved(db, a, approver=_approver(db))
        db.commit()
        assert ex.allapot == "failed"
        assert "ész" in (ex.eredmeny or {}).get("blokk_ok", "") or "leállítás" in (ex.eredmeny or {}).get("blokk_ok", "")
    finally:
        _beallitas(db, module=False, side=False, kill=False)
        db.commit()
        _takarits(db, t)


def test_eltero_hash_blokkol(db):
    """6: a jóváhagyás más hash-re szól, mint a javaslat → blokkolt (új kell)."""
    _beallitas(db, module=True, side=True)
    t, p, a = _feladat_javaslat_jovahagyas(db, payload_hash_override="masik_hash")
    try:
        ex = execute_approved(db, a, approver=_approver(db))
        db.commit()
        assert ex.allapot == "failed"
        assert "elavult" in (ex.eredmeny or {}).get("blokk_ok", "").lower()
    finally:
        _beallitas(db, module=False, side=False)
        db.commit()
        _takarits(db, t)


def test_consumed_jovahagyas_blokkol(db):
    """5: már felhasznált jóváhagyással nincs újabb végrehajtás."""
    _beallitas(db, module=True, side=True)
    t, p, a = _feladat_javaslat_jovahagyas(db)
    from app.admin_agent.executor import _most

    a.allapot = ApprovalState.CONSUMED.value
    a.felhasznalt_at = _most()
    db.flush()
    try:
        ex = execute_approved(db, a, approver=_approver(db))
        db.commit()
        assert ex.allapot == "failed"
    finally:
        _beallitas(db, module=False, side=False)
        db.commit()
        _takarits(db, t)


def test_idempotens_egy_execution_rekord(db):
    """7: kétszer meghívva EGY végrehajtási rekord marad (dupla kattintás)."""
    _beallitas(db, module=False, side=False)
    t, p, a = _feladat_javaslat_jovahagyas(db)
    try:
        execute_approved(db, a, approver=_approver(db))
        db.commit()
        execute_approved(db, a, approver=_approver(db))
        db.commit()
        assert db.query(ActionExecution).filter_by(proposal_id=p.id).count() == 1
    finally:
        _takarits(db, t)
