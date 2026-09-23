"""Lara: tanulás az AI asszisztens munkájából.

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
VALÓDI MODELLHÍVÁS NINCS - az asszisztens beszélgetését közvetlenül rögzítjük.

Fedi: a lezárt kérés-körből (kérdés + válasz + végrehajtott / elutasított
művelet) tudás-jelölt lesz a műveletből adódó témában; a futó kört és a
jóváhagyásra váró műveletet nem dolgozza fel; változatlan kört nem ír újra,
új fejleménynél frissít; jóváhagyás után a partner szerint előkerül; a
kikapcsolt forrás és a vészleállítás megállítja.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
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


def _bekapcsol(db, be=True):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.engedett_forrasok = {**(s.engedett_forrasok or {}), "asszisztens": be}
    s.kill_switch = False
    db.flush()


def _beszelgetes(db, *, fut=False):
    from app.models.ai_beszelgetes import AiBeszelgetes, AiMuvelet, AiUzenet
    from app.models.employee import Employee, EmployeeType

    e = Employee(full_name="Asszisztens Tesztelő", tipus=EmployeeType.BELSOS)
    db.add(e)
    db.flush()
    b = AiBeszelgetes(employee_id=e.id, cim="teszt", fut=fut)
    db.add(b)
    db.flush()
    t0 = datetime.now(timezone.utc) - timedelta(minutes=30)
    k1 = AiUzenet(beszelgetes_id=b.id, szerep="felhasznalo", created_at=t0,
                  szoveg="Vedd fel a Fénymester Stúdió Kft. szeptemberi bérleti számláját a DEMO26-P014 kiadásai közé.",
                  adat={"kontextus": {"utvonal": "/penzugyek", "cim": "Pénzügyek"}})
    db.add(k1)
    db.flush()
    db.add(AiUzenet(beszelgetes_id=b.id, szerep="esemeny", szoveg="lépés", created_at=t0 + timedelta(seconds=5)))
    m1 = AiMuvelet(beszelgetes_id=b.id, employee_id=e.id, idempotencia_kulcs="k1", method="POST", path="/api/v1/expenses",
                   keres={"megnevezes": "Stúdióbérlés", "partner": "Fénymester Stúdió Kft.", "netto": 150000},
                   osszefoglalo="Kiadás felvétele a DEMO26-P014 projektkódra", allapot="vegrehajtva", valasz_status=201,
                   created_at=t0 + timedelta(seconds=10))
    m2 = AiMuvelet(beszelgetes_id=b.id, employee_id=e.id, idempotencia_kulcs="k2", method="DELETE",
                   path="/api/v1/expenses/999", osszefoglalo="A régi, duplikált kiadás törlése", allapot="elutasitva",
                   created_at=t0 + timedelta(seconds=20))
    db.add_all([m1, m2])
    db.flush()
    v1 = AiUzenet(beszelgetes_id=b.id, szerep="asszisztens", created_at=t0 + timedelta(seconds=30),
                  szoveg="Felvettem a kiadást a DEMO26-P014 projektkódra. A régi tétel törlését elutasítottad, megmaradt.")
    k2 = AiUzenet(beszelgetes_id=b.id, szerep="felhasznalo", szoveg="Mennyi a kintlévőség?", created_at=t0 + timedelta(minutes=1))
    db.add_all([v1, k2])
    db.flush()
    db.add(AiUzenet(beszelgetes_id=b.id, szerep="asszisztens", szoveg="5 170 000 Ft.", created_at=t0 + timedelta(minutes=1, seconds=5)))
    db.flush()
    return b, k1, k2, m1


def _chunk(db, uzenet_id):
    from app.models.admin_agent import MemoryChunk

    return db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"asszisztens:{uzenet_id}"))


def test_lezart_korbol_tudas_jelolt_temaval_es_elutasitassal(db):
    from app.admin_agent.asszisztens import asszisztens_tanulas

    _bekapcsol(db)
    b, k1, k2, _ = _beszelgetes(db)
    e = asszisztens_tanulas(db)
    assert e["allapot"] == "kesz" and e["uj"] >= 2
    m = _chunk(db, k1.id)
    assert m.hatokor == "szamla" and m.ervenyes is False and m.minosites == "jelolt"
    t = m.tartalom
    assert "Asszisztens Tesztelő" in t and "oldal: Pénzügyek" in t
    assert "Fénymester Stúdió Kft. szeptemberi bérleti számláját" in t
    assert "✓ végrehajtva: POST /api/v1/expenses" in t and "partner: Fénymester Stúdió Kft." in t
    assert "ELUTASÍTOTTA: DELETE /api/v1/expenses/999" in t
    assert "Felvettem a kiadást" in t
    m2 = _chunk(db, k2.id)
    assert m2.hatokor == "asszisztens" and "Művelet nem történt" in m2.tartalom


def test_futo_kor_es_fuggo_muvelet_var_valtozatlant_nem_irja_ujra(db):
    from app.admin_agent.asszisztens import asszisztens_tanulas

    _bekapcsol(db)
    b, k1, k2, m1 = _beszelgetes(db, fut=True)
    asszisztens_tanulas(db)
    assert _chunk(db, k1.id) is not None  # lezárt (nem utolsó) kör
    assert _chunk(db, k2.id) is None  # az utolsó kör még fut

    b.fut = False
    m1.allapot = "fuggo"
    db.flush()
    e = asszisztens_tanulas(db)
    assert e["folyamatban"] >= 1  # a jóváhagyásra váró művelet köre vár

    # Új fejlemény a körben (a művelet végül lefutott, más válasszal) → új verzió.
    m1.allapot = "vegrehajtva"
    m1.valasz_status = 200
    db.flush()
    elso = asszisztens_tanulas(db)
    masodik = asszisztens_tanulas(db)
    assert masodik["feldolgozott_kor"] == 0 and elso["feldolgozott_kor"] >= 1


def test_jovahagyas_utan_partner_szerint_elokerul_es_kapcsolok(db):
    from app.admin_agent.asszisztens import asszisztens_tanulas
    from app.admin_agent.memory import kapcsolodo_tudas
    from app.admin_agent.settings_service import get_settings

    _bekapcsol(db)
    _, k1, _, _ = _beszelgetes(db)
    asszisztens_tanulas(db)
    assert kapcsolodo_tudas(db, hatokor="szamla", partner="Fénymester Stúdió Kft.")["hasonlo_esetek"] == []
    _chunk(db, k1.id).ervenyes = True
    db.flush()
    talalat = kapcsolodo_tudas(db, hatokor="szamla", partner="Fénymester Stúdió Kft.")["hasonlo_esetek"]
    assert talalat and "DEMO26-P014" in talalat[0]["tartalom"]

    _bekapcsol(db, be=False)
    assert asszisztens_tanulas(db)["allapot"] == "kikapcsolva"
    _bekapcsol(db)
    get_settings(db).kill_switch = True
    db.flush()
    assert asszisztens_tanulas(db)["allapot"] == "leallitva"
