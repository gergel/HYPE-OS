"""Lara önellenőrzése — a válaszok beszámítása a pontosságba, és a vizsga a
régi adaton (véletlen adag / teljes).

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.idoszak import Idoszak, terulet_osszegzes
from app.admin_agent.observer import tanulas_kezdete
from app.admin_agent.onellenorzes import onellenorzes, valaszol
from app.admin_agent.onellenorzes_bovitett import bovitett_ellenorzes
from app.models.admin_agent import LaraKerdes
from app.models.megrendeloi_papir import MegrendeloiTig
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


_n = [0]


def _kod(db, megrendelo: str, *, regi: bool = False, **kw) -> ProjectCode:
    _n[0] += 1
    pc = ProjectCode(projektkod=f"ADK-{_n[0]}-{id(db) % 10000}", megrendelo_neve=megrendelo,
                     project_nev="Adatkör teszt", datum=date.today(), **kw)
    if regi:
        pc.created_at = tanulas_kezdete(db) - timedelta(days=40 + _n[0])
    db.add(pc)
    db.flush()
    return pc


def test_pontossag_beszamitja_a_valaszokat():
    """A „hibás rögzítés" Lara javára, a megtanult eset helyesnek számít, a
    kivétel kimarad — a vak arány változatlan mellette."""
    c = Counter(egyezik=8, elter=2, megmadyarazva=0)
    c.update({"megmagyarazva": 2, "lara_helyes": 1, "kivetel": 1})
    t = terulet_osszegzes(c, nem_tudta=False)
    assert t["talalati_arany"] == 0.8
    assert t["pontossag"] == round(9 / 9, 3) and t["nyitott_elteres"] == 0


def test_hibas_valasz_utan_nem_rontja_a_pontossagot(db):
    """Megrendelői TIG +ÁFA: Lara +ÁFA-t várt, ÁFA nélkül lett → kérdés; a
    „hibás rögzítés" válasz után az eset Lara javára számít."""
    kezdet = tanulas_kezdete(db)
    for afa in (True, True, False):
        pc = _kod(db, "Pontosság Teszt Zrt.")
        db.add(MegrendeloiTig(project_code_id=pc.id, ceg_neve="Pontosság Teszt Zrt.", allapot="Kiküldve",
                              plusz_afa=afa, netto_osszeg=100000))
    db.flush()
    t0, cs = bovitett_ellenorzes(db, Idoszak(tol=kezdet))
    g = next(g for k, g in cs.items() if g.get("terulet") == "megrendeloi_tig" and g["partner"] == "Pontosság Teszt Zrt.")
    k = LaraKerdes(tipus=g.pop("tipus"), allapot="nyitott", kulcs="adk|afa", partner_nev=g["partner"], kerdes="?", kontextus=g)
    db.add(k)
    db.flush()
    valaszol(db, k, valasz_tipus="hibas", magyarazat=None, user_id=2, elesithet=False)
    t1, _ = bovitett_ellenorzes(db, Idoszak(tol=kezdet))
    e0, e1 = t0["megrendeloi_tig"], t1["megrendeloi_tig"]
    assert e1["lara_helyes"] == e0["lara_helyes"] + 1
    assert e1["talalati_arany"] == e0["talalati_arany"]  # a vak arány szigorú marad
    assert e1["pontossag"] > e0["pontossag"]


def test_vizsga_a_regi_adaton_veletlen_adag_es_teljes(db):
    """A tanulás kezdete előtti rekordokat a fő kör nem nézi, a vizsga igen;
    a véletlen adag a mag szerint változik, a teljes vizsga mindet nézi."""
    kezdet = tanulas_kezdete(db)
    for pn in (False, False, False, True):
        _kod(db, "Régi Adat Teszt Kft.", regi=True, papir_nelkul=pn)
    _, fo = bovitett_ellenorzes(db, Idoszak(tol=kezdet))
    assert not any(g.get("partner") == "Régi Adat Teszt Kft." for g in fo.values())
    teljes = Idoszak(tol=None, ertekel_ig=kezdet, arany=1.0, nev="teljes")
    t, cs = bovitett_ellenorzes(db, teljes)
    g = next(g for g in cs.values() if g.get("partner") == "Régi Adat Teszt Kft." and g.get("dimenzio") == "papir_nelkul")
    assert len(g["esetek"]) == 1 and "fogalom" not in t

    azonok = [f"projektkod:{i}" for i in range(400)]
    most = datetime.now(timezone.utc) - timedelta(days=400)
    a = {x for x in azonok if Idoszak(tol=None, ertekel_ig=kezdet, arany=0.3, mag="1", nev="minta").ertekel(x, most)}
    b = {x for x in azonok if Idoszak(tol=None, ertekel_ig=kezdet, arany=0.3, mag="2", nev="minta").ertekel(x, most)}
    assert 60 < len(a) < 180 and a != b
    assert not Idoszak(tol=None, ertekel_ig=kezdet, nev="teljes").ertekel("x", datetime.now(timezone.utc))


def test_onellenorzes_vizsgaval_jelolt_regi_kerdes(db, monkeypatch):
    from app.admin_agent import osszesito

    monkeypatch.setattr(osszesito, "kerdes_ertesites", lambda *_a, **_k: 0)
    for k in db.scalars(select(LaraKerdes).where(LaraKerdes.allapot == "nyitott")).all():
        k.allapot = "elvetve"
    for pn in (False, False, False, True):
        _kod(db, "Régi Kérdés Teszt Kft.", regi=True, papir_nelkul=pn)
    r = onellenorzes(db, trigger="onellenorzes:teszt", teljes_vizsga=True)
    assert r["vizsga"]["mod"] == "teljes" and r["vizsga"]["ellenorzott"] >= 4
    assert "pontossag" in r and "pontossag" in r["teruletek"]["projektkod"]
    k = db.scalar(select(LaraKerdes).where(LaraKerdes.partner_nev == "Régi Kérdés Teszt Kft."))
    assert k is not None and k.kontextus.get("regi_adat") and k.kerdes.startswith("Régi adatból")
    assert r["vizsga_kerdes"] <= 3
