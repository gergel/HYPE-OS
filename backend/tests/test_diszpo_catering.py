"""A diszpó-szöveg catering-mondata a stáb létszámához igazodik (a
felhasználó kérése): egy embernek egyes szám, többnek többes szám.

Az adatbázisos rész tranzakcióban fut, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.employee import Employee
from app.models.project import Project
from app.services.diszpo_sablon import (
    CATERING_EGYES,
    CATERING_TOBBES,
    DISZPO_SZOVEG_SABLON,
    catering_a_letszamhoz,
)


def test_szovegcsere():
    assert CATERING_TOBBES in DISZPO_SZOVEG_SABLON
    egy = catering_a_letszamhoz(DISZPO_SZOVEG_SABLON, 1)
    assert CATERING_EGYES in egy and CATERING_TOBBES not in egy
    assert "Catering: nem biztosított, így igény esetén készülj magadnak kérlek szendviccsel" in egy
    assert catering_a_letszamhoz(egy, 3) == DISZPO_SZOVEG_SABLON
    # Stáb nélkül nem nyúl hozzá; átfogalmazott szöveghez sem.
    assert catering_a_letszamhoz(DISZPO_SZOVEG_SABLON, 0) == DISZPO_SZOVEG_SABLON
    assert catering_a_letszamhoz("Catering lesz (demó)", 1) == "Catering lesz (demó)"


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


def test_menteskor_a_stabhoz_igazodik(db):
    emberek = db.scalars(select(Employee).order_by(Employee.id).limit(2)).all()
    assert len(emberek) == 2
    p = Project(nev="Catering teszt (demó)", diszpo_szovege=DISZPO_SZOVEG_SABLON)
    db.add(p)
    db.flush()
    assert CATERING_TOBBES in p.diszpo_szovege  # stáb nélkül marad

    p.crew = [emberek[0]]
    db.flush()
    assert CATERING_EGYES in p.diszpo_szovege

    p.crew = list(emberek)
    db.flush()
    assert CATERING_TOBBES in p.diszpo_szovege

    p.crew = [emberek[1]]
    db.flush()
    assert CATERING_EGYES in p.diszpo_szovege
