"""Kiadás felvezetésekor LEHETSÉGES DUPLIKÁCIÓ (a felhasználó kérése, 2026-10):
ugyanaz a dátum + összeg + cég → 409 a találatokkal; engedéssel mégis felvihető.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.routes.finance import _expense_before_create
from app.core.database import engine
from app.models.finance import Expense
from app.services import kiadas_duplikacio

NAP = date(2026, 9, 15)


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


@pytest.fixture
def meglevo(db):
    e = Expense(megnevezes="Fotó Bérlés Kft. (demó)", kiadas_leiras="Objektív bérlés", netto=100_000, brutto=127_000,
                fizetes_datuma=NAP, tipus="egyeb")
    db.add(e)
    db.flush()
    return e


def _adat(**kw) -> dict:
    alap = {"megnevezes": "fotó bérlés  kft. (DEMÓ)", "netto": 100_000, "brutto": 127_000, "fizetes_datuma": NAP,
            "tipus": "egyeb"}
    return alap | kw


def test_egyezo_kiadas_409_a_talalattal(db, meglevo):
    with pytest.raises(HTTPException) as exc:
        _expense_before_create(_adat(), db)
    assert exc.value.status_code == 409
    d = exc.value.detail
    assert d["kod"] == kiadas_duplikacio.KOD and d["tetelek"][0]["id"] == meglevo.id
    assert d["tetelek"][0]["href"] == f"/penzugyek/kiadas/{meglevo.id}"


def test_engedessel_megis_felviheto_es_a_jelzo_kikerul(db, meglevo):
    adat = _expense_before_create(_adat(duplikacio_engedve=True), db)
    assert "duplikacio_engedve" not in adat
    db.add(Expense(**adat))
    db.flush()


@pytest.mark.parametrize("valtozas", [
    {"fizetes_datuma": date(2026, 9, 16)},       # más nap
    {"netto": 100_010, "brutto": 127_013},       # más összeg (> 1 Ft)
    {"megnevezes": "Másik Cég Kft. (demó)"},     # más cég
])
def test_nem_egyezo_kiadas_atmegy(db, meglevo, valtozas):
    _expense_before_create(_adat(**valtozas), db)


def test_afa_szamitasbol_jovo_brutto_is_egyezik(db, meglevo):
    # Csak nettó + „+ÁFA 27%” - a szerver számolja ki a bruttót, és azzal is egyezik.
    with pytest.raises(HTTPException):
        _expense_before_create(_adat(brutto=None, plusz_afa="igen", afa_szazalek=27), db)


def test_datum_vagy_osszeg_nelkul_nem_ellenoriz(db, meglevo):
    _expense_before_create(_adat(fizetes_datuma=None), db)
    _expense_before_create(_adat(netto=None, brutto=None), db)
