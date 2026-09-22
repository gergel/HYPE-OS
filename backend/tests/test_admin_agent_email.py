"""Admin-Ágens — E fázis (e-mail-előkészítés) és eszköztár-invariánsok tesztjei.

Fedi: automata-hurok elleni védelem (10./21.), a „Beállítás szükséges" valós
állapot integráció hiányában, és hogy banki utalást VÉGREHAJTÓ eszköz nincs
regisztrálva (10.: R3, tiltott).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.executor import TOOL_REGISTRY, _validate_email_valasz
from app.admin_agent.proposals import keszit_javaslat
from app.models.admin_agent import ActionProposal, ActionTrace, AdminTask, AgentRun, Approval


def test_email_validacio_automata_cimzett_tiltott():
    # no-reply / mailer-daemon / bounce → nem küldünk (körkörös hurok elleni védelem).
    for cim in ["no-reply@ceg.hu", "mailer-daemon@x.com", "bounce@y.hu", "postmaster@z.hu"]:
        hibak = _validate_email_valasz({"to": [cim], "subject": "x", "html_body": "y"})
        assert any("Automatikus" in h for h in hibak), cim


def test_email_validacio_hianyzo_mezok():
    hibak = _validate_email_valasz({"to": [], "subject": "", "html_body": ""})
    assert any("címzett" in h.lower() for h in hibak)
    assert any("tárgy" in h.lower() for h in hibak)
    assert any("szöveg" in h.lower() for h in hibak)


def test_email_validacio_valid():
    assert _validate_email_valasz({"to": ["partner@ceg.hu"], "subject": "Tárgy", "html_body": "<p>Szia</p>"}) == []


def test_nincs_banki_vegrehajto_eszkoz():
    # Banki utalást INDÍTÓ/aláíró/végrehajtó eszköz szándékosan NINCS.
    for eszkoz in TOOL_REGISTRY:
        assert "bank" not in eszkoz.lower()
    # Az utalás feladattípushoz sincs regisztrált (mellékhatásos) eszköz.
    assert not any(s.tipus == "utalas" for s in TOOL_REGISTRY.values())


def test_email_kockazat_r2():
    assert TOOL_REGISTRY["email.valasz_kuldes"].risk.value == "R2"
    assert TOOL_REGISTRY["email.valasz_kuldes"].side_effect is True


# ── DB-integrációs teszt (Postgres) ─────────────────────────────────────────


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


def _takarits(db, t: AdminTask) -> None:
    pids = [p.id for p in db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).all()]
    if pids:
        db.query(Approval).filter(Approval.proposal_id.in_(pids)).delete(synchronize_session=False)
    db.query(ActionTrace).filter(ActionTrace.task_id == t.id).delete(synchronize_session=False)
    db.query(ActionProposal).filter(ActionProposal.task_id == t.id).delete(synchronize_session=False)
    db.query(AgentRun).filter(AgentRun.task_id == t.id).delete(synchronize_session=False)
    db.query(AdminTask).filter(AdminTask.id == t.id).delete(synchronize_session=False)
    db.commit()


def test_keszit_javaslat_email_beallitas_szukseges(db):
    """Gmail-integráció nélkül a valid e-mail-javaslat sem véglegesíthető:
    DRAFT marad, a feladat NEEDS_INFO, és az ellenőrzés jelzi a „Beállítás
    szükséges" okot (valós állapot, nem hamis siker)."""
    t = AdminTask(tipus="email", altipus="valasz", cim="Válasz a partnernek", allapot="new", trust_level="L0")
    db.add(t)
    db.flush()
    try:
        payload = {"to": ["partner@ceg.hu"], "subject": "Re: ajánlat", "html_body": "<p>Köszönjük</p>"}
        proposal, dontes = keszit_javaslat(db, t, eszkoz="email.valasz_kuldes", payload=payload)
        db.commit()
        assert proposal.kockazat == "R2"
        # Gmail nincs konfigurálva a teszt-környezetben → DRAFT + NEEDS_INFO.
        assert proposal.allapot == "draft"
        assert t.allapot == "needs_info"
        assert proposal.ellenorzesek is not None and proposal.ellenorzesek["integracio_ok"] is False
        # Nem jött létre jóváhagyás (hiányos javaslathoz nem).
        assert db.query(Approval).filter_by(proposal_id=proposal.id).count() == 0
    finally:
        _takarits(db, t)
