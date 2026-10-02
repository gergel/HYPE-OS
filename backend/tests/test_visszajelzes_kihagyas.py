"""A vágói visszajelzés kihagyása: ahol az anyaghoz tartozó forgatáson stáb
dolgozott, ott NEM hagyható ki (a felhasználó kérése).

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.project import Project
from app.services import deliverable_actions


@pytest.fixture
def db():
    with engine.connect() as conn:
        tx = conn.begin()
        sess = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield sess
        finally:
            sess.close()
            tx.rollback()


def _anyag(db, stab: list[Employee]) -> Deliverable:
    p = Project(nev="Forgatás (demó)", forgatas_datuma=date(2026, 9, 1))
    p.crew = stab
    db.add(p)
    db.flush()
    d = Deliverable(projekt_neve="Anyag (demó)", project_id=p.id)
    db.add(d)
    db.flush()
    return d


def test_stabos_forgatasnal_nem_hagyhato_ki(db):
    ember = db.scalars(select(Employee).where(Employee.full_name.is_not(None)).limit(1)).first()
    assert ember is not None
    anyag = _anyag(db, [ember])
    assert deliverable_actions.kihagyhato_a_visszajelzes(db, anyag) is False
    with pytest.raises(ValueError, match="nem hagyható ki"):
        deliverable_actions.send_visszajelzes(db, anyag, ember, kihagyas_indoka="Nincs időm (demó)")
    # Kitöltve viszont rendben megy.
    fb = deliverable_actions.send_visszajelzes(db, anyag, ember, technikai_helyesseg=8)
    assert fb.kihagyva is not True


def test_stab_nelkuli_forgatasnal_kihagyhato(db):
    ember = db.scalars(select(Employee).limit(1)).first()
    anyag = _anyag(db, [])
    assert deliverable_actions.kihagyhato_a_visszajelzes(db, anyag) is True
    fb = deliverable_actions.send_visszajelzes(db, anyag, ember, kihagyas_indoka="Nem volt forgatás (demó)")
    assert fb.kihagyva is True


def test_forgatas_nelkuli_anyagnal_kihagyhato(db):
    ember = db.scalars(select(Employee).limit(1)).first()
    anyag = Deliverable(projekt_neve="Önálló anyag (demó)")
    db.add(anyag)
    db.flush()
    assert deliverable_actions.kihagyhato_a_visszajelzes(db, anyag) is True


def test_csak_projektkodhoz_kotott_anyag_kihagyhato_akkor_is_ha_a_kod_mas_forgatasan_volt_stab(db):
    from app.models.project_code import ProjectCode

    ember = db.scalars(select(Employee).where(Employee.full_name.is_not(None)).limit(1)).first()
    kod = ProjectCode(projektkod="HYPE99-9901")
    db.add(kod)
    db.flush()
    p = Project(nev="Stábos forgatás (demó)", forgatas_datuma=date(2026, 9, 1), project_code_id=kod.id)
    p.crew = [ember]
    db.add(p)
    db.flush()
    # Ugyanazon a kódon egy forgatás NÉLKÜLI anyag - kihagyható.
    anyag = Deliverable(projekt_neve="Forgatás nélküli anyag (demó)", project_code_id=kod.id)
    db.add(anyag)
    db.flush()
    assert deliverable_actions.kihagyhato_a_visszajelzes(db, anyag) is True
    fb = deliverable_actions.send_visszajelzes(db, anyag, ember, kihagyas_indoka="Archív anyag (demó)")
    assert fb.kihagyva is True
