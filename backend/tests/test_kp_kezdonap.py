"""KP forgalom kezdőnap (2026.01.01) és a Pénzügyek két egyenlege.

- A kezdőnap előtti KP forgalom sor NEM létezik: se a naplóban, se az
  egyenlegben, se a táblában/egyenként lekérve, se Lara rendszerfigyelésében.
- A régi "Profit (idén)" helyett KP egyenleg + SZÁMLA egyenleg (bankszámla).

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError


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


def _kp(db, datum, osszeg, forgalom="bevetel", megnevezes="KP-KEZDONAP teszt (demó)"):
    from app.models.finance import KpForgalom

    sor = KpForgalom(kiadas_datuma=datum, osszeg=osszeg, forgalom=forgalom, megnevezes=megnevezes)
    db.add(sor)
    db.flush()
    return sor


def test_regi_kp_sor_nem_letezik(db):
    from app.api.routes.finance import _kp_forgalom_kezdonap_ota
    from app.models.finance import KpForgalom
    from app.services import kassza

    elotte = kassza.kep(db).egyenleg
    regi = _kp(db, date(2025, 12, 31), 1_000_000)
    uj_be = _kp(db, date(2026, 2, 1), 50_000)
    uj_ki = _kp(db, date(2026, 3, 1), 20_000, forgalom="kiadas")
    datum_nelkul = _kp(db, None, 5_000)

    kep = kassza.kep(db)
    idk = {s.id for s in kep.sorok}
    assert regi.id not in idk
    assert {uj_be.id, uj_ki.id, datum_nelkul.id} <= idk
    # Az egyenlegbe csak a kezdőnap óta felvett (és a dátum nélküli) sor számít.
    assert kep.egyenleg - elotte == pytest.approx(50_000 - 20_000 + 5_000)
    # A havi bontás nyitó egyenlege is csak ezekből a sorokból jön: régebbi
    # sor nincs, amiből összeadódhatna.
    assert all(s.datum is None or s.datum >= kassza.KP_KEZDET for s in kep.sorok)

    # A CRUD-lista és az egyenkénti lekérés szűrője.
    latszik = set(db.scalars(_kp_forgalom_kezdonap_ota(select(KpForgalom.id), db, None)).all())
    assert regi.id not in latszik and uj_be.id in latszik


def test_lara_sem_latja_a_regi_kp_sort(db):
    from app.admin_agent.rendszer import _figyelt_tablak

    t = _figyelt_tablak(db)["kp_forgalmak"]
    elotte = db.scalar(select(func.count()).select_from(t))
    _kp(db, date(2024, 5, 5), 123)
    assert db.scalar(select(func.count()).select_from(t)) == elotte
    _kp(db, date(2026, 5, 5), 123)
    assert db.scalar(select(func.count()).select_from(t)) == elotte + 1


def test_kp_es_szamla_egyenleg(db):
    from app.api.routes.finance import finance_summary
    from app.models.finance import Expense, Revenue

    ma = date.today()
    elotte = finance_summary(db=db, _user=None)
    assert not hasattr(elotte, "ytd_profit")

    db.add_all([
        # Számlára érkező bevétel: számít.
        Revenue(netto=80_000, brutto=100_000, fizetes_datuma=ma, fizetes_modja="Átutalás"),
        # Készpénzes bevétel és pénzmozgás nélküli: a számlát nem mozgatja.
        Revenue(netto=50_000, brutto=50_000, fizetes_datuma=ma, fizetes_modja="Készpénz"),
        Revenue(netto=7_000, brutto=7_000, fizetes_datuma=ma, fizetes_modja="Nincs pénzmozgás"),
        # Utalt kiadás: számít; készpénzes és pénzmozgás nélküli: nem.
        Expense(megnevezes="KP-KEZDONAP kiadás (demó)", netto=24_000, brutto=30_000, fizetes_datuma=ma, kesz=True, kifizetes_modja="Átutalás"),
        Expense(megnevezes="KP-KEZDONAP kiadás (demó)", netto=9_000, brutto=9_000, fizetes_datuma=ma, kesz=True, kifizetes_modja="Készpénz"),
        Expense(megnevezes="KP-KEZDONAP kiadás (demó)", netto=3_000, brutto=3_000, fizetes_datuma=ma, kesz=True, kifizetes_modja="Nincs pénzmozgás"),
    ])
    db.flush()
    # ATM-felvétel: a kasszába érkezik, a számláról megy ki.
    _kp(db, ma, 20_000, megnevezes="KP felvétel ATM (demó)")

    utana = finance_summary(db=db, _user=None)
    # A számla egyenleg NETTÓBAN számol (a bruttó 100 000 / 30 000 nem).
    assert utana.szamla_be - elotte.szamla_be == pytest.approx(80_000)
    assert utana.szamla_atvezetes - elotte.szamla_atvezetes == pytest.approx(20_000)
    assert utana.szamla_ki - elotte.szamla_ki == pytest.approx(24_000 + 20_000)
    assert utana.szamla_egyenleg - elotte.szamla_egyenleg == pytest.approx(80_000 - 24_000 - 20_000)
    # A KP egyenleg a házipénztár egyenlege: KP bevétel + ATM - KP kiadás.
    assert utana.kp_egyenleg == utana.kassza.egyenleg
    assert utana.kp_egyenleg - elotte.kp_egyenleg == pytest.approx(50_000 + 20_000 - 9_000)
