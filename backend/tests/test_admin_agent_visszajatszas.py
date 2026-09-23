"""Admin-Ágens — visszajátszás a rögzített számlákon, partner-szabályok, kézi
szabályfelvétel.

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
VALÓDI MODELLHÍVÁS NINCS (a kulcs kikapcsolva).

Fedi: az érkeztető eredeti javaslata vs a végső emberi döntés → egyezik / eltér
/ nem javasolt; ebből példa-jelölt (nem éles) és találati arány; partnerenként
egybehangzó döntésekből szabály-JELÖLT (nem aktív); idempotencia; a tanulás
kezdete előtti számla kimarad; az ÉLESÍTETT partner-szabály modell nélkül is
kitölti az üres célt, de az érkeztető javaslatát nem írja felül; a partner-
egyezés cégformától/ékezettől független; a kézi szabály validálása.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import llm


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


@pytest.fixture(autouse=True)
def _modell_nelkul(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    llm.teszt_adapter(None)


def _kod(db, kod):
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod=kod)
    db.add(pc)
    db.flush()
    return pc


def _rogzitett(db, *, partner, javaslat, cel_tipus, pc=None, mikor=None):
    from app.models.bejovo_szamla import ALLAPOT_JOVAHAGYVA, BejovoSzamla

    b = BejovoSzamla(
        allapot=ALLAPOT_JOVAHAGYVA, kibocsato_nev=partner, szamlaszam=f"VJ-{partner[:4]}",
        netto=10000, brutto=12700, penznem="HUF", javaslat=javaslat, cel_tipus=cel_tipus,
        cel_project_code_id=pc.id if pc else None, jovahagyva_at=mikor or datetime.now(timezone.utc),
    )
    db.add(b)
    db.flush()
    return b


def test_visszajatszas_egyezik_elter_nem_javasolt_es_szabaly_jelolt(db):
    from app.admin_agent.visszajatszas import osszesites, visszajatszas
    from app.models.admin_agent import MemoryChunk, PlaybookRule

    visszajatszas(db)  # a már meglévő (dev) számlák feldolgozása — innen mérünk
    elotte = osszesites(db)

    a, b = _kod(db, "VJTESZT-A"), _kod(db, "VJTESZT-B")
    p = "Visszajátszó Partner EV"
    e1 = _rogzitett(db, partner=p, javaslat={"tipus": "kiadas_uj", "javasolt_cel": {"cel_project_code_id": a.id}},
                    cel_tipus="kiadas_uj", pc=a)
    e2 = _rogzitett(db, partner=p, javaslat={"tipus": "kiadas_uj", "javasolt_cel": {"cel_project_code_id": a.id}},
                    cel_tipus="kiadas_uj", pc=b)
    e3 = _rogzitett(db, partner="Visszajátszó Partner", javaslat={"tipus": None}, cel_tipus="kiadas_uj", pc=b)
    regi = _rogzitett(db, partner=p, javaslat={"tipus": "mukodesi"}, cel_tipus="kiadas_uj", pc=a,
                      mikor=datetime(2026, 8, 20, tzinfo=timezone.utc))

    r = visszajatszas(db)
    db.flush()
    assert r["uj_szamla"] == 3 and r["uj_pelda"] == 3  # a régi (aug.) kimarad
    utana = osszesites(db)
    assert utana["egyezik"] - elotte["egyezik"] == 1
    assert utana["elter"] - elotte["elter"] == 1
    assert utana["nem_javasolt"] - elotte["nem_javasolt"] == 1

    peldak = {m.forras: m for m in db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("visszajatszas:%"))).all()}
    assert peldak[f"visszajatszas:bejovo:{e1.id}"].ervenyes is False  # jelölt — nem éles
    assert "Az érkeztető is ezt javasolta" in peldak[f"visszajatszas:bejovo:{e1.id}"].tartalom
    assert "tévesen" in peldak[f"visszajatszas:bejovo:{e2.id}"].tartalom
    assert "VJTESZT-B" in peldak[f"visszajatszas:bejovo:{e2.id}"].tartalom
    assert "nem tudott javaslatot" in peldak[f"visszajatszas:bejovo:{e3.id}"].tartalom
    assert f"visszajatszas:bejovo:{regi.id}" not in peldak

    # A három eset (cégformától függetlenül) EGY partner → szabály-JELÖLT, nem aktív.
    szabaly = [
        x for x in db.scalars(select(PlaybookRule)).all()
        if (x.feltetelek or {}).get("forras") == "visszajatszas" and (x.feltetelek or {}).get("partner") == "visszajatszo partner"
    ]
    assert len(szabaly) == 1
    assert szabaly[0].allapot == "pending" and szabaly[0].feltetelek["cel_tipus"] == "kiadas_uj"
    assert szabaly[0].feltetelek["projektkod_idk"] == []  # eltérő kódok → kódot nem rögzít

    # Idempotencia: újrafuttatva nincs új esemény, példa vagy szabály.
    r2 = visszajatszas(db)
    assert r2["uj_szamla"] == 0 and r2["uj_pelda"] == 0 and r2["uj_szabaly_jelolt"] == 0


def _szamla_ellenorzendo(db, partner, **kw):
    from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, BejovoSzamla

    alap = dict(allapot=ALLAPOT_ELLENORZENDO, kibocsato_nev=partner, szamlaszam="SZT-1",
                netto=5000, brutto=6350, penznem="HUF", javaslat={})
    alap.update(kw)
    b = BejovoSzamla(**alap)
    db.add(b)
    db.flush()
    return b


def _aktiv_szabaly(db, partner_kulcs, cel_tipus, kodok):
    from app.models.admin_agent import PlaybookRule

    r = PlaybookRule(hatokor="szamla", cim=f"teszt {partner_kulcs}", tartalom="teszt", allapot="active", verzio=1,
                     prioritas=10, feltetelek={"partner": partner_kulcs, "cel_tipus": cel_tipus, "projektkod_idk": kodok})
    db.add(r)
    db.flush()
    return r


def test_elesitett_partner_szabaly_modell_nelkul_kitolti_az_ures_celt(db):
    from app.admin_agent.pipeline_szamla import arnyek_elemzes
    from app.models.admin_agent import ActionProposal

    pc = _kod(db, "SZABTESZT-1")
    r = _aktiv_szabaly(db, "szabaly teszt", "kiadas_uj", [pc.id])
    b = _szamla_ellenorzendo(db, "Szabály Teszt Kft.")
    t = arnyek_elemzes(db, b)
    db.flush()
    p = db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).first()
    assert p.payload["cel_tipus"] == "kiadas_uj"
    assert p.payload["cel_project_code_id"] == pc.id
    assert p.ellenorzesek["szabaly"]["szabaly_id"] == r.id
    assert t.uncertainty == 0.3


def test_partner_szabaly_nem_irja_felul_az_erkeztetot(db):
    from app.admin_agent.pipeline_szamla import arnyek_elemzes
    from app.models.admin_agent import ActionProposal

    _aktiv_szabaly(db, "felulir teszt", "kiadas_uj", [])
    b = _szamla_ellenorzendo(db, "Felülír Teszt Bt.", cel_tipus="mukodesi")
    t = arnyek_elemzes(db, b)
    db.flush()
    p = db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).first()
    assert p.payload["cel_tipus"] == "mukodesi"
    assert any("aktív szabály" in f for f in p.ellenorzesek.get("figyelmeztetesek", []))


def test_partner_egyezes_cegformatol_fuggetlen_es_szabaly_csak_a_partnernel(db):
    from app.admin_agent.memory import kapcsolodo_tudas
    from app.models.admin_agent import MemoryChunk

    db.add(MemoryChunk(hatokor="szamla", tartalom="Beérkező számla — Zseni Boglárka: helyes besorolás X.",
                       ervenyes=True, minosites="jovahagyott"))
    _aktiv_szabaly(db, "zseni boglarka", "kiadas_uj", [])
    _aktiv_szabaly(db, "mas partner nev", "mukodesi", [])
    db.flush()
    t = kapcsolodo_tudas(db, hatokor="szamla", partner="Zseni Boglárka EV")
    assert any("Zseni Boglárka" in e["tartalom"] for e in t["hasonlo_esetek"])
    cimek = [s["cim"] for s in t["szabalyok"]]
    assert "teszt zseni boglarka" in cimek
    assert "teszt mas partner nev" not in cimek


def test_kezi_szabaly_validalas_es_letrehozas(db):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app
    from app.models.admin_agent import PlaybookRule

    c = TestClient(app)
    h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
    ut = "/api/v1/admin-agent/rules"
    alap = {"hatokor": "szamla", "cim": "Kézi teszt-szabály", "tartalom": "Mindig a forgatási kódra."}
    assert c.post(ut, headers=h, json={**alap, "cel_tipus": "kiadas_uj"}).status_code == 400  # partner nélkül
    assert c.post(ut, headers=h, json={**alap, "partner": "Kézi Partner Kft.", "projektkod": "NINCS-ILYEN-999"}).status_code == 400
    assert c.post(ut, headers=h, json={**alap, "hatokor": "ismeretlen"}).status_code == 400
    r = c.post(ut, headers=h, json={**alap, "partner": "Kézi Partner Kft.", "cel_tipus": "mukodesi"})
    assert r.status_code == 200, r.text
    d = r.json()
    try:
        assert d["allapot"] == "draft"  # nem éles: értékelés + élesítés kell
        assert d["feltetelek"]["partner"] == "kezi partner" and d["feltetelek"]["cel_tipus"] == "mukodesi"
        assert d["prioritas"] >= 10
    finally:
        db.query(PlaybookRule).filter(PlaybookRule.id == d["id"]).delete(synchronize_session=False)
        db.commit()
