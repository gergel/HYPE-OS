"""Lara — egyetlen felelős (Vidor Gergely): minden hozzá fut be, másnak Lara
nem küld semmit.

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback
(az API-teszt a saját sorait maga törli)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import osszesito
from app.admin_agent.settings_service import get_settings, lara_felelos
from app.models.admin_agent import AdminTask, LaraKerdes
from app.models.employee import Employee, EmployeeType
from app.models.notification import Notification


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


def _limitek(db, **kv):
    s = get_settings(db)
    s.limitek = {k: v for k, v in {**(s.limitek or {}), **kv}.items() if v is not None}
    db.flush()


def _ember(db, nev: str, email: str | None = None) -> Employee:
    e = Employee(full_name=nev, tipus=EmployeeType.BELSOS, is_active=True, email=email)
    db.add(e)
    db.flush()
    return e


def test_felelos_nev_szerint_es_beallitassal(db):
    """Beállítás nélkül név szerint (ékezet/sorrend nem számít) Vidor Gergely;
    a beállított felelős felülírja."""
    _limitek(db, felelos_employee_id=None)
    for e in db.scalars(select(Employee).where(Employee.full_name.ilike("%vidor%"))).all():
        e.is_active = False
    v = _ember(db, "Gergely Vidor")
    assert lara_felelos(db).id == v.id
    masik = _ember(db, "Másik Felelős Teszt")
    _limitek(db, felelos_employee_id=masik.id)
    assert lara_felelos(db).id == masik.id


def test_ertesites_csak_a_felelosnek(db):
    """„Csak a felelősnek" módban a kérdés-értesítés és az összesítő címzettje
    KIZÁRÓLAG a felelős; ha nincs felelős, senki."""
    v = _ember(db, "Felelős Teszt Vidor")
    _limitek(db, felelos_employee_id=v.id, csak_felelosnek=True, kerdes_ertesites=True)
    assert [e.id for e in osszesito.lara_felelosok(db)] == [v.id]
    assert [e.id for e in osszesito.lara_felelosok(db, muvelet="delete")] == [v.id]
    k = LaraKerdes(tipus="szamla_besorolas", allapot="nyitott", kulcs="fel|1", partner_nev="Felelős Kft.",
                   kerdes="?", kontextus={"esetek": []})
    db.add(k)
    db.flush()
    assert osszesito.kerdes_ertesites(db, [k]) == 1
    uj = db.scalars(select(Notification).where(Notification.kind == "lara_kerdes").order_by(Notification.id.desc())).first()
    assert uj.employee_id == v.id

    v.is_active = False
    _limitek(db, felelos_employee_id=None)
    for e in db.scalars(select(Employee).where(Employee.full_name.ilike("%vidor%gergely%"))).all():
        e.is_active = False
    db.flush()
    assert osszesito.lara_felelosok(db) == []


def test_feladat_ertesites_allapotvaltaskor(db):
    """Ellenőrzésre / jóváhagyásra váró feladat → értesítés a felelősnek,
    ugyanabban az állapotban újra nem."""
    v = _ember(db, "Feladat Felelős Teszt")
    _limitek(db, felelos_employee_id=v.id, csak_felelosnek=True, feladat_ertesites=True)
    t = AdminTask(tipus="szamla", cim="Felelős teszt-feladat", allapot="awaiting_approval", trust_level="L0")
    db.add(t)
    db.flush()
    assert osszesito.feladat_ertesites(db, t, "new") == 1
    n = db.scalars(select(Notification).where(Notification.kind == "lara_feladat").order_by(Notification.id.desc())).first()
    assert n.employee_id == v.id and n.link == f"/admin-agent/munkasor/{t.id}" and "jóváhagyásra vár" in n.message
    assert osszesito.feladat_ertesites(db, t, "awaiting_approval") == 0


def test_executor_mas_nem_dont_es_mas_cimre_nem_megy_level(db):
    """A végrehajtó őr: nem a felelős jóváhagyása blokkolt; a felelős jóváhagyta
    levél is blokkolt, ha nem a saját címére menne."""
    from app.admin_agent.enums import TaskType
    from app.admin_agent.executor import execute_approved
    from app.admin_agent.proposals import _hash
    from app.models.admin_agent import ActionProposal, Approval

    v = _ember(db, "Executor Felelős Teszt", email="felelos-teszt@example.com")
    idegen = _ember(db, "Executor Idegen Teszt")
    s = get_settings(db)
    s.module_enabled, s.side_effects_enabled, s.kill_switch = True, True, False
    _limitek(db, felelos_employee_id=v.id, csak_felelosnek=True)
    from app.models.admin_agent import TrustPolicy

    for tp in db.scalars(select(TrustPolicy).where(TrustPolicy.tipus == "email")).all():
        tp.szint = "L2"
    db.add(TrustPolicy(tipus="email", altipus=None, szint="L2"))
    t = AdminTask(tipus=TaskType.EMAIL.value, cim="Levél teszt", allapot="awaiting_approval", trust_level="L2", kockazat="R2")
    db.add(t)
    db.flush()
    payload = {"to": ["partner@example.com"], "subject": "Teszt", "body": "Szia"}
    p = ActionProposal(task_id=t.id, eszkoz="email.valasz_kuldes", payload=payload, payload_hash=_hash(payload),
                       allapot="ready", kockazat="R2")
    db.add(p)
    db.flush()
    a = Approval(proposal_id=p.id, payload_hash=p.payload_hash, allapot="approved")
    db.add(a)
    db.flush()
    ex = execute_approved(db, a, approver=idegen)
    assert ex.allapot == "failed" and "felelőse" in ex.eredmeny["blokk_ok"]

    a2 = Approval(proposal_id=p.id, payload_hash=p.payload_hash, allapot="approved")
    db.add(a2)
    db.flush()
    ex2 = execute_approved(db, a2, approver=v)
    assert ex2.allapot == "failed"
    assert "partner@example.com" in ex2.eredmeny["blokk_ok"] and "csak a felelősének" in ex2.eredmeny["blokk_ok"]


def test_jovahagyas_vegpont_orsege(db):
    """A jóváhagyás/elutasítás-végpont őre: más 403, a felelős átmegy; ha nincs
    felelős, senki nem dönthet (403 beszédes üzenettel)."""
    from fastapi import HTTPException

    from app.api.routes.admin_agent import _csak_a_felelos_donthet

    v = _ember(db, "Döntés Felelős Teszt")
    masik = _ember(db, "Döntés Idegen Teszt")
    _limitek(db, felelos_employee_id=v.id, csak_felelosnek=True)
    _csak_a_felelos_donthet(db, v)
    with pytest.raises(HTTPException) as e:
        _csak_a_felelos_donthet(db, masik)
    assert e.value.status_code == 403 and "Döntés Felelős Teszt" in e.value.detail
    _limitek(db, csak_felelosnek=False)
    _csak_a_felelos_donthet(db, masik)  # kikapcsolt módban a régi jogosultság dönt


def test_api_feladat_felelose_es_jovahagyas_zar(db):
    """Új feladat felelőse a felelős (akkor is, ha a kérés mást adott meg); a
    Beállítások mutatja a felelőst és a módot."""
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    s = get_settings(db)
    regi = dict(s.limitek or {})
    v = _ember(db, "API Felelős Teszt")
    s.limitek = {**regi, "felelos_employee_id": v.id, "csak_felelosnek": True}
    db.commit()
    vid = v.id
    tid = None
    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
        r = c.post("/api/v1/admin-agent/tasks", headers=h, json={"tipus": "szamla", "cim": "Felelős API teszt", "felelos_id": 2})
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        assert r.json()["felelos_id"] == vid
        r = c.get("/api/v1/admin-agent/settings", headers=h)
        assert r.json()["felelos"]["id"] == vid and r.json()["csak_felelosnek"] is True
    finally:
        s = get_settings(db)
        s.limitek = regi
        if tid:
            db.query(AdminTask).filter(AdminTask.id == tid).delete(synchronize_session=False)
        db.query(Employee).filter(Employee.id == vid).delete(synchronize_session=False)
        db.commit()
