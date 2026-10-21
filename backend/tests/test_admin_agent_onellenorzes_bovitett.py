"""Lara — bővített önellenőrzés: megrendelői papírok, projektkód-döntések,
bevétel, belsős TIG, elvárás-ellenőrzés és rendszer-fogalmak; kérdés és
válasz → tudás / javítási feladat.

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.onellenorzes import onellenorzes, valaszol
from app.admin_agent.onellenorzes_bovitett import bovitett_ellenorzes
from app.models.admin_agent import AdminTask, LaraKerdes, MemoryChunk
from app.models.project_code import ProjectCode


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


KEZDET = datetime(2026, 9, 1, tzinfo=timezone.utc)
_n = [0]


def _kod(db, megrendelo: str, **kw) -> ProjectCode:
    _n[0] += 1
    pc = ProjectCode(projektkod=f"BOV-{_n[0]}-{id(db) % 10000}", megrendelo_neve=megrendelo,
                     project_nev="Bővített teszt", datum=date.today(), **kw)
    db.add(pc)
    db.flush()
    return pc


def _tig(db, megrendelo: str, afa: bool):
    from app.models.megrendeloi_papir import MegrendeloiTig

    pc = _kod(db, megrendelo)
    t = MegrendeloiTig(project_code_id=pc.id, ceg_neve=megrendelo, allapot="Kiküldve", plusz_afa=afa, netto_osszeg=100000)
    db.add(t)
    db.flush()
    return t


def test_megrendeloi_tig_afa_elteres_kerdes_es_valasz(db):
    for _ in range(2):
        _tig(db, "Bővített Áfás Zrt.", True)
    uj = _tig(db, "Bővített Áfás Zrt.", False)
    _, cs = bovitett_ellenorzes(db, KEZDET)
    g = next(g for g in cs.values() if g.get("terulet") == "megrendeloi_tig" and g.get("dimenzio") == "afa"
             and g["partner"] == "Bővített Áfás Zrt.")
    assert [e["rekord"] for e in g["esetek"]] == [f"megrendeloi_tig:{uj.id}"]
    assert "+ÁFA számítottam" in __import__("app.admin_agent.onellenorzes_bovitett", fromlist=["x"]).kerdes_szoveg(g)

    # Kérdés → „mindig így" → tudás; ugyanerre az esetre nincs új kérdés.
    k = LaraKerdes(tipus=g.pop("tipus"), allapot="nyitott", kulcs="teszt|afa", partner_nev=g["partner"], kerdes="?",
                   kontextus=g)
    db.add(k)
    db.flush()
    e = valaszol(db, k, valasz_tipus="mindig", magyarazat="Mostantól alanyi mentes.", user_id=2, elesithet=False)
    m = db.get(MemoryChunk, e["pelda_id"])
    assert m.ervenyes and "Megrendelői TIG" in m.tartalom and "alanyi mentes" in m.tartalom
    _, cs2 = bovitett_ellenorzes(db, KEZDET)
    assert not any(g2.get("terulet") == "megrendeloi_tig" and g2["partner"] == "Bővített Áfás Zrt." for g2 in cs2.values())

    # „Mostantól így": az újabb, ÁFA nélküli TIG rendben; az újabb +ÁFA-s már kérdés.
    from datetime import datetime, timedelta, timezone

    kesobb = datetime.now(timezone.utc) + timedelta(hours=1)
    rendben = _tig(db, "Bővített Áfás Zrt.", False)
    rendben.updated_at = kesobb
    fura = _tig(db, "Bővített Áfás Zrt.", True)
    fura.updated_at = kesobb
    db.flush()
    _, cs3 = bovitett_ellenorzes(db, KEZDET)
    esetek = [e["rekord"] for g3 in cs3.values() if g3.get("terulet") == "megrendeloi_tig"
              and g3["partner"] == "Bővített Áfás Zrt." for e in g3["esetek"]]
    assert esetek == [f"megrendeloi_tig:{fura.id}"]


def test_projektkod_papir_nelkul_varatlan(db):
    pc = _kod(db, "Papírnélküli Teszt Kft.", papir_nelkul=True)
    _, cs = bovitett_ellenorzes(db, KEZDET)
    g = next(g for g in cs.values() if g.get("dimenzio") == "papir_nelkul" and g["partner"] == "Papírnélküli Teszt Kft.")
    assert g["esetek"][0]["rekord"] == f"projektkod:{pc.id}" and "indoklás nélkül" in g["valosag"]["szoveg"]


def test_bevetel_kesese_a_szokashoz_kepest(db):
    from app.models.finance import Revenue

    for nap in (0, 2):
        pc = _kod(db, "Pontos Fizető Zrt.")
        db.add(Revenue(project_code_id=pc.id, netto=1, fizetes_hatarideje=date(2026, 9, 5),
                       fizetes_datuma=date(2026, 9, 5) + timedelta(days=nap)))
    pc = _kod(db, "Pontos Fizető Zrt.")
    db.add(Revenue(project_code_id=pc.id, netto=1, fizetes_hatarideje=date(2026, 9, 5), fizetes_datuma=date(2026, 10, 20)))
    db.flush()
    _, cs = bovitett_ellenorzes(db, KEZDET)
    g = next(g for g in cs.values() if g.get("dimenzio") == "keses" and g["partner"] == "Pontos Fizető Zrt.")
    assert len(g["esetek"]) == 1 and "45 nap késés" in g["valosag"]["szoveg"]


def test_elvaras_fizetve_papir_nelkul_hiba_valasz_feladatot_keszit(db):
    from app.models.finance import Revenue

    pc = _kod(db, "Elvárás Teszt Zrt.")
    db.add(Revenue(project_code_id=pc.id, netto=500000, fizetes_datuma=date(2026, 9, 20)))
    db.flush()
    _, cs = bovitett_ellenorzes(db, KEZDET)
    ck, g = next((ck, g) for ck, g in cs.items()
                 if g.get("ellenorzes") == "fizetve_papir_nelkul" and g["partner"] == "Elvárás Teszt Zrt.")
    k = LaraKerdes(tipus=g.pop("tipus"), allapot="nyitott", kulcs=ck, partner_nev=g["partner"], kerdes="?", kontextus=g)
    db.add(k)
    db.flush()
    e = valaszol(db, k, valasz_tipus="hibas", magyarazat="Elmaradt a TIG.", user_id=2, elesithet=False)
    t = db.get(AdminTask, e["feladat_id"])
    assert t.tipus == "egyeb" and t.project_code_id == pc.id and "Javítandó" in t.cim
    _, cs2 = bovitett_ellenorzes(db, KEZDET)
    assert ck not in cs2  # az eset megválaszolva — nem kérdez újra


def test_alvallalkozo_kifizetve_papir_nelkul(db):
    from app.models.employee import Employee, EmployeeType
    from app.models.finance import Expense

    emp = Employee(full_name="Papírtalan Alvállalkozó", tipus=EmployeeType.KULSOS)
    db.add(emp)
    db.flush()
    pc = _kod(db, "Alvállalkozó Teszt Zrt.")
    db.add(Expense(megnevezes="Papírtalan Alvállalkozó", netto=80000, brutto=80000, kesz=True, tipus="kulsos",
                   employee_id=emp.id, project_code_id=pc.id))
    db.flush()
    _, cs = bovitett_ellenorzes(db, KEZDET)
    assert any(g.get("ellenorzes") == "alvallalkozo_papir_nelkul" and g["partner"] == "Papírtalan Alvállalkozó"
               for g in cs.values())


def test_fogalom_kerdes_adagolva_es_valasz_kotelezo_szoveggel(db):
    from app.admin_agent.onellenorzes import ValaszHiba
    from app.models.finance import Expense

    for i in range(4):
        db.add(Expense(megnevezes=f"Fogalom Teszt {i}", netto=1, brutto=1, tipus="fogalomteszt_ertek"))
    db.flush()
    _, cs = bovitett_ellenorzes(db, KEZDET)
    fog = [g for g in cs.values() if g.get("tipus") == "rendszer_fogalom"]
    assert 0 < len(fog) <= 3
    g = fog[0]
    ck = next(ck for ck, x in cs.items() if x is g)
    k = LaraKerdes(tipus=g.pop("tipus"), allapot="nyitott", kulcs=ck, partner_nev=g["partner"], kerdes="?", kontextus=g)
    db.add(k)
    db.flush()
    with pytest.raises(ValaszHiba):
        valaszol(db, k, valasz_tipus="magyarazat", magyarazat=None, user_id=2, elesithet=False)
    e = valaszol(db, k, valasz_tipus="magyarazat", magyarazat="Ez egy teszt-állapot.", user_id=2, elesithet=False)
    assert "Rendszer-fogalom" in db.get(MemoryChunk, e["pelda_id"]).tartalom
    _, cs2 = bovitett_ellenorzes(db, KEZDET)
    assert ck not in cs2


def test_onellenorzes_futas_kerdez_es_teruleteket_mutat(db, monkeypatch):
    from app.admin_agent import osszesito

    _kod(db, "Futás Teszt Kft.", szamla_kihagyva=True)
    monkeypatch.setattr(osszesito, "kerdes_ertesites", lambda *_a, **_k: 0)  # értesítés nélkül
    r = onellenorzes(db, trigger="onellenorzes:teszt")
    assert {"megrendeloi_szerzodes", "megrendeloi_tig", "projektkod", "bevetel", "belsos_tig", "elvaras",
            "fogalom"} <= set(r["teruletek"])
    assert db.scalar(select(LaraKerdes).where(LaraKerdes.tipus == "admin_dontes",
                                               LaraKerdes.partner_nev == "Futás Teszt Kft.")) is not None
