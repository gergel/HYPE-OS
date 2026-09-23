"""Lara — tudásháló (a megtanult tudás kapcsolati gráfja).

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, rollback.
Fedi: a gráf CSAK valós tudásból épül; a jóváhagyott példa erősebb kapcsolat,
mint a jelölt; az elvetett nem kerül bele; a partner a cégformától függetlenül
egy pont; a szabály a partnerhez/célhoz kötődik; minden kapcsolatnak van első
megjelenése (a növekedés lejátszásához).
"""

from __future__ import annotations

from datetime import datetime, timezone

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


def _vj(db, bid, partner, tipus, kod_id, pelda_allapot):
    from app.models.admin_agent import MemoryChunk, SourceEvent

    db.add(SourceEvent(forras="visszajatszas", forras_azonosito=f"bejovo:{bid}", forras_verzio="v1",
                       allapot="feldolgozva",
                       metaadat={"partner": partner, "vegso": {"tipus": tipus, "projektkod_idk": [kod_id]},
                                 "jovahagyva_at": datetime.now(timezone.utc).isoformat()}))
    if pelda_allapot:
        db.add(MemoryChunk(hatokor="szamla", tartalom=f"{partner} teszt", forras=f"visszajatszas:bejovo:{bid}",
                           ervenyes=pelda_allapot == "jovahagyott", visszavont=pelda_allapot == "elvetett",
                           minosites=pelda_allapot))
    db.flush()


def test_tudashalo_valos_tudasbol(db):
    from app.admin_agent.tudashalo import tudashalo
    from app.models.admin_agent import PlaybookRule
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod="HALO-TESZT-1")
    db.add(pc)
    db.flush()
    _vj(db, 990001, "Hálóteszt Partner EV", "kiadas_uj", pc.id, "jovahagyott")
    _vj(db, 990002, "Hálóteszt Partner", "kiadas_uj", pc.id, "jovahagyott")
    _vj(db, 990003, "Gyenge Jelölt Kft.", "mukodesi", None, "jelolt")
    _vj(db, 990004, "Elvetett Partner Bt.", "mukodesi", None, "elvetett")
    db.add(PlaybookRule(hatokor="szamla", cim="Hálóteszt szabály", tartalom="x", allapot="active", verzio=1,
                        feltetelek={"partner": "haloteszt partner", "cel_tipus": "kiadas_uj"}))
    db.flush()

    g = tudashalo(db)
    pontok = {p["id"]: p for p in g["pontok"]}
    elek = {tuple(sorted((e["a"], e["b"]))): e for e in g["elek"]}

    # A cégformától függetlenül EGY partner-pont; a témához és a projektkódhoz kötve.
    assert "partner:haloteszt partner" in pontok
    assert pontok["partner:haloteszt partner"]["tema"] == "szamla"
    erős = elek[tuple(sorted(("partner:haloteszt partner", f"kod:{pc.id}")))]
    assert erős["jovahagyott"] == 2 and erős["bizonyossag"] > 0.5 and erős["t"]
    # Jelölt → gyenge kapcsolat; elvetett → nincs a hálóban.
    gyenge = elek[tuple(sorted(("tema:szamla", "partner:gyenge jelolt")))]
    assert gyenge["bizonyossag"] < erős["bizonyossag"]
    assert "partner:elvetett partner" not in pontok
    # Az élesített szabály a partnerhez és a célhoz kötődik.
    szabaly = next(p for p in g["pontok"] if p["fajta"] == "szabaly" and p["cimke"] == "Hálóteszt szabály")
    assert tuple(sorted((szabaly["id"], "partner:haloteszt partner"))) in elek
    assert tuple(sorted((szabaly["id"], "cel:kiadas_uj"))) in elek
    # Váz: a mag mind az öt témakörhöz (számla, TIG, szerződés, e-mail, AI asszisztens).
    assert sum(1 for e in g["elek"] if e.get("vaz")) == 6  # utalás nincs; AI asszisztens és Projektek van
    assert g["osszesites"]["kapcsolatok"] >= 4


def test_tudashalo_api(db):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    r = TestClient(app).get("/api/v1/admin-agent/knowledge-graph",
                            headers={"Authorization": f"Bearer {create_access_token('2', 'admin')}"})
    assert r.status_code == 200
    d = r.json()
    assert {"pontok", "elek", "osszesites", "tanulas_kezdete"} <= set(d)
    assert any(p["fajta"] == "core" for p in d["pontok"])
