"""D fázis: egy üzleti ügy = egy eset, elkülönített vizsgakészlet.
Postgres nélkül a DB-s részek self-skip; a végén rollback."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import ugyek


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


def test_ugy_kulcs_projektkoddal_kozos_anelkul_dokumentumonkent():
    a = ugyek.ugy_kulcs(partner="Minta Kft.", projektkod_idk=[7, 3], sajat="bejovo:1")
    b = ugyek.ugy_kulcs(partner="MINTA kft", projektkod_idk=[3, 7], sajat="bejovo:2")
    assert a == b and a.startswith("pk:3,7|")
    assert ugyek.ugy_kulcs(partner="Minta Kft.", sajat="bejovo:1") != ugyek.ugy_kulcs(partner="Minta Kft.", sajat="bejovo:2")
    assert ugyek.ugy_kulcs(partner=None) is None
    assert ugyek.meta_ugy_kulcs({"partner": "Minta Kft.", "vegso": {"projektkod_idk": [3, 7]}}, sajat="x") == a
    assert ugyek.meta_ugy_kulcs({"partner": "Minta Kft.", "project_code_id": 3}, sajat="x").startswith("pk:3|")


def test_vizsga_besorolas_stabil_es_aranyos():
    kulcsok = [f"pk:{i}|p:minta" for i in range(2000)]
    elso = [ugyek.vizsga_e(k, 0.2) for k in kulcsok]
    assert elso == [ugyek.vizsga_e(k, 0.2) for k in kulcsok]  # determinisztikus
    assert 0.15 < sum(elso) / len(elso) < 0.25
    assert not ugyek.vizsga_e(None)


def test_vizsgakeszlet_alapbol_ki(db):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    lim = dict(s.limitek or {})
    lim.pop("vizsgakeszlet", None)
    s.limitek = lim
    db.flush()
    assert ugyek.vizsgakeszlet_be(db) is False
    kiz = ugyek.kizart(db)
    assert not any(kiz(f"pk:{i}|p:x") for i in range(200))
    s.limitek = {**lim, "vizsgakeszlet": True}
    db.flush()
    kiz = ugyek.kizart(db)
    assert any(kiz(f"pk:{i}|p:x") for i in range(200))


def test_tudas_ugyeket_szamol_nem_szamlakat(db):
    """Három számla UGYANARRA a projektkódra egy ügy → nincs általánosítás;
    két külön projektkód két ügy → van."""
    from app.admin_agent.onellenorzes import Tudas

    t = Tudas(db, kizart=lambda _k: False)
    t.szabalyok.clear()
    t.esetek.clear()
    t.esetek["ugyteszt partner"] = [(1, "kiadas_uj", (5,)), (2, "kiadas_uj", (5,)), (3, "kiadas_uj", (5,))]
    assert t.cel("ugyteszt partner") is None
    t.esetek["ugyteszt partner"] += [(4, "kiadas_uj", (6,))]
    c = t.cel("ugyteszt partner")
    assert c is not None and c["tipus"] == "kiadas_uj" and "2 jóváhagyott korábbi ügy" in c["forras"]
    # Projektkód nélkül minden számla külön ügy.
    t.esetek["havidij partner"] = [(10, "erezsi", ()), (11, "erezsi", ())]
    assert t.cel("havidij partner")["tipus"] == "erezsi"
    # A vizsgakészlet ügyei kimaradnak.
    t2 = Tudas(db, kizart=lambda k: k.startswith("pk:6|"))
    t2.szabalyok.clear()
    t2.esetek.clear()
    t2.esetek["ugyteszt partner"] = t.esetek["ugyteszt partner"]
    assert t2.cel("ugyteszt partner") is None
