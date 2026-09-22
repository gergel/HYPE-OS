"""Admin-Ágens — számla-felvezetés L0 árnyék-elemzés integrációs tesztje.

A pipeline JSONB-t és JSONB-lekérdezést használ (a feladat idempotenciája a
``forras_referenciak`` mezőre épül), ezért ez VALÓS Postgres ellen fut (nem
SQLite). Ha az adatbázis nem elérhető, a teszt kihagyja magát. Minden általa
létrehozott sort a végén takarít.

Amit rögzít (a master prompt 8./10. invariánsai):
- L0-ban SEMMILYEN üzleti rekord nem jön létre (Expense-szám nem változik).
- A javaslat a meglévő pénzügyi szolgáltatás belépőjére mutat
  (``szamla_erkeztetes.jovahagy``), de nem hajtódik végre.
- A döntést a policy engine hozza: modul KI → BLOCKED (árnyék).
- Idempotens: ugyanaz a számla ugyanabban az állapotban nem duplikál.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.pipeline_szamla import arnyek_elemzes
from app.models.admin_agent import (
    ActionProposal,
    ActionTrace,
    AdminTask,
    AgentRun,
    Approval,
    SourceEvent,
)
from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, BejovoSzamla
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


def _takarits(db, bejovo_id: int) -> None:
    tasks = db.scalars(
        select(AdminTask).where(AdminTask.forras_referenciak["bejovo_szamla_id"].astext == str(bejovo_id))
    ).all()
    for t in tasks:
        propok = db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).all()
        pids = [p.id for p in propok]
        db.query(ActionTrace).filter(ActionTrace.task_id == t.id).delete(synchronize_session=False)
        if pids:
            db.query(Approval).filter(Approval.proposal_id.in_(pids)).delete(synchronize_session=False)
        db.query(ActionProposal).filter(ActionProposal.task_id == t.id).delete(synchronize_session=False)
        db.query(AgentRun).filter(AgentRun.task_id == t.id).delete(synchronize_session=False)
        db.query(AdminTask).filter(AdminTask.id == t.id).delete(synchronize_session=False)
    db.query(SourceEvent).filter(
        SourceEvent.forras == "bejovo_szamla", SourceEvent.forras_azonosito == str(bejovo_id)
    ).delete(synchronize_session=False)
    db.query(BejovoSzamla).filter(BejovoSzamla.id == bejovo_id).delete(synchronize_session=False)
    db.commit()


def test_arnyek_elemzes_l0_nincs_mellekhatas_es_idempotens(db):
    exp_elott = db.query(Expense).count()
    bejovo = BejovoSzamla(
        allapot=ALLAPOT_ELLENORZENDO,
        kibocsato_nev="Teszt Szállító Kft.",
        szamlaszam="TESZT-AA-PYTEST-1",
        netto=10000,
        brutto=12700,
        penznem="HUF",
        cel_tipus="mukodesi",
        javaslat={"cel_tipus": "mukodesi"},
    )
    db.add(bejovo)
    db.commit()
    bid = bejovo.id
    try:
        task = arnyek_elemzes(db, bejovo, trigger="manual")
        db.commit()

        # A feladat elkészült, R2 kockázattal, árnyék (BLOCKED) állapotban.
        assert task.tipus == "szamla"
        assert task.kockazat == "R2"
        assert task.allapot == "proposal_ready"  # modul KI → BLOCKED → árnyék
        assert task.blokkolo_ok  # a policy indoka

        # Pontosan egy javaslat, a MEGLÉVŐ szolgáltatás belépőjére mutatva.
        propok = db.scalars(select(ActionProposal).where(ActionProposal.task_id == task.id)).all()
        assert len(propok) == 1
        assert propok[0].eszkoz == "szamla_erkeztetes.jovahagy"
        assert propok[0].kockazat == "R2"
        assert propok[0].payload_hash

        # Nyomvonal (elemzés + policy-döntés) és futás rögzült; jóváhagyás NEM
        # jött létre (BLOCKED, nem NEEDS_APPROVAL).
        assert db.query(ActionTrace).filter_by(task_id=task.id).count() >= 2
        assert db.query(AgentRun).filter_by(task_id=task.id).count() == 1
        assert db.query(Approval).filter_by(proposal_id=propok[0].id).count() == 0

        # IDEMPOTENCIA: ugyanabban az állapotban újrafuttatva nem duplikál.
        task2 = arnyek_elemzes(db, bejovo, trigger="manual")
        db.commit()
        assert task2.id == task.id
        assert (
            db.query(SourceEvent)
            .filter_by(forras="bejovo_szamla", forras_azonosito=str(bid))
            .count()
            == 1
        )
        assert (
            db.query(AdminTask)
            .filter(AdminTask.forras_referenciak["bejovo_szamla_id"].astext == str(bid))
            .count()
            == 1
        )

        # SEMMILYEN üzleti mellékhatás: az Expense-ek száma változatlan.
        assert db.query(Expense).count() == exp_elott
    finally:
        _takarits(db, bid)


def test_arnyek_elemzes_hianyos_javaslat_needs_info(db):
    """Ha a cél/összeg hiányzik, a determinista ellenőrzés hiányosnak jelöli, és
    a feladat NEEDS_INFO lesz (jóváhagyás mellett sem mehetne végrehajtásra)."""
    bejovo = BejovoSzamla(
        allapot=ALLAPOT_ELLENORZENDO,
        kibocsato_nev="Hiányos Kft.",
        szamlaszam="TESZT-AA-PYTEST-2",
        penznem="HUF",
    )
    db.add(bejovo)
    db.commit()
    bid = bejovo.id
    try:
        task = arnyek_elemzes(db, bejovo, trigger="manual")
        db.commit()
        assert task.allapot == "needs_info"
        assert task.blokkolo_ok
        propok = db.scalars(select(ActionProposal).where(ActionProposal.task_id == task.id)).all()
        assert len(propok) == 1
        # Hiányos javaslat: DRAFT (nem véglegesíthető payload).
        assert propok[0].allapot == "draft"
    finally:
        _takarits(db, bid)
