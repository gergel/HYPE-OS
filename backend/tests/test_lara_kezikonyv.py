"""Lara rendszerkézikönyve: tervezet → jóváhagyás → verzió, technikai vs üzleti,
jogosultság szerinti keresés. Postgres nélkül self-skip; a végén rollback."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import kezikonyv as kk
from app.models.admin_agent import MemoryChunk


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


def _szakasz(kulcs, tartalom, oldal=None):
    return {"kulcs": f"teszt:{kulcs}", "cim": f"Tesztszakasz {kulcs} (demó)", "tartalom": tartalom,
            "forras_tipus": "modell", "oldal": oldal}


def test_forras_szakaszok_modellbol_mezo_megjegyzessel():
    sz = {s["kulcs"]: s for s in kk.forras_szakaszok()}
    m = sz["modell:MemoryChunk"]
    assert "aa_memory_chunks" in m["tartalom"]
    # A `#:` mező-megjegyzés bekerül a technikai leírásba.
    assert "holdout" in m["tartalom"]
    assert sz["modell:Expense"]["oldal"] == "/penzugyek"


def test_tervezet_nem_hasznalhato_jovahagyas_utan_igen(db):
    e = kk.tervezet_generalas(db, szakaszok=[_szakasz("a", "A zümmögőkassza a tesztelt pénzmozgás (demó).")])
    assert e == {"uj": 1, "uj_verzio": 0, "valtozatlan": 0}
    m = db.scalars(select(MemoryChunk).where(MemoryChunk.forras == "kezikonyv:teszt:a")).one()
    assert m.minosites == kk.TERVEZET and m.ervenyes is False and m.tudas_fajta == kk.TECHNIKAI
    assert kk.kereses(db, "zümmögőkassza pénzmozgás") == []

    # Idempotens: változatlan forrásra nem jön új sor.
    assert kk.tervezet_generalas(db, szakaszok=[_szakasz("a", "A zümmögőkassza a tesztelt pénzmozgás (demó).")])[
        "valtozatlan"] == 1

    kk.jovahagy(db, m.id, None)
    db.flush()
    assert m.felhasznalhato_at is not None and m.jovahagyva_at is not None
    talalat = kk.kereses(db, "zümmögőkassza pénzmozgás")
    assert [t["id"] for t in talalat] == [m.id]


def test_uj_verzio_a_regit_nem_torli_jovahagyasig_a_regi_ervenyes(db):
    kk.tervezet_generalas(db, szakaszok=[_szakasz("b", "Brekegőnapló első változat (demó) szöveg.")])
    v1 = db.scalars(select(MemoryChunk).where(MemoryChunk.forras == "kezikonyv:teszt:b")).one()
    kk.jovahagy(db, v1.id, None)
    db.flush()
    e = kk.tervezet_generalas(db, szakaszok=[_szakasz("b", "Brekegőnapló második változat (demó) szöveg.")])
    assert e["uj_verzio"] == 1
    v2 = db.scalars(select(MemoryChunk).where(MemoryChunk.elozo_verzio_id == v1.id)).one()
    assert v2.verzio == 2 and v2.ervenyes is False
    # Amíg a v2 nincs jóváhagyva, a v1 a használható.
    assert [t["id"] for t in kk.kereses(db, "brekegőnapló változat")] == [v1.id]
    kk.jovahagy(db, v2.id, None)
    db.flush()
    assert [t["id"] for t in kk.kereses(db, "brekegőnapló változat")] == [v2.id]
    assert v1.ervenyes_ig is not None and db.get(MemoryChunk, v1.id) is not None
    assert [x["verzio"] for x in kk.verziok(db, v1.id)] == [2, 1]


def test_uzleti_eljaras_kulon_fajta_es_elorebb_sorolodik(db):
    kk.tervezet_generalas(db, szakaszok=[_szakasz("c", "Csiripelőszámla technikai leírás (demó) mezőkkel.")])
    t = db.scalars(select(MemoryChunk).where(MemoryChunk.forras == "kezikonyv:teszt:c")).one()
    kk.jovahagy(db, t.id, None)
    u = kk.uzleti_tervezet(db, cim="Csiripelőszámla eljárás (demó)", tartalom="A csiripelőszámlát mindig péntekig rögzítjük (demó).")
    assert u.tudas_fajta == kk.UZLETI and u.ervenyes is False
    kk.jovahagy(db, u.id, None)
    db.flush()
    ids = [x["id"] for x in kk.kereses(db, "csiripelőszámla")]
    assert ids[0] == u.id and t.id in ids
    with pytest.raises(kk.KezikonyvHiba):
        kk.tervezet_szerkesztes(db, u.id, "Átírás jóváhagyott szakaszon")


def test_jogosultsag_a_keresesben(db):
    kk.tervezet_generalas(db, szakaszok=[_szakasz("d", "Dörmögőegyenleg pénzügyi leírás (demó).", oldal="/penzugyek")])
    m = db.scalars(select(MemoryChunk).where(MemoryChunk.forras == "kezikonyv:teszt:d")).one()
    kk.jovahagy(db, m.id, None)
    db.flush()
    assert kk.kereses(db, "dörmögőegyenleg", engedelyezett=lambda o: False) == []
    assert [x["id"] for x in kk.kereses(db, "dörmögőegyenleg", engedelyezett=lambda o: True)] == [m.id]


def test_elvetett_tervezet_nem_hagyhato_jova_es_nem_jon_vissza(db):
    kk.tervezet_generalas(db, szakaszok=[_szakasz("e", "Elvetendő szakasz szövege (demó) hosszabban.")])
    m = db.scalars(select(MemoryChunk).where(MemoryChunk.forras == "kezikonyv:teszt:e")).one()
    kk.elvet(db, m.id)
    with pytest.raises(kk.KezikonyvHiba):
        kk.jovahagy(db, m.id, None)
    assert kk.tervezet_generalas(db, szakaszok=[_szakasz("e", "Elvetendő szakasz szövege (demó) hosszabban.")])[
        "valtozatlan"] == 1


def test_a_memoria_vegpontok_nem_kezelik_a_kezikonyvet(db):
    """A Tudástár általános jóváhagyása nem kerülheti meg a kézikönyv verziózását."""
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user
    from app.main import app
    from app.core.database import get_db
    from app.models.employee import Employee

    admin = db.get(Employee, 2)
    if admin is None:
        pytest.skip("Nincs admin.")
    kk.tervezet_generalas(db, szakaszok=[_szakasz("f", "Fütyülőszakasz szövege (demó) hosszabban.")])
    m = db.scalars(select(MemoryChunk).where(MemoryChunk.forras == "kezikonyv:teszt:f")).one()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    orig_commit = db.commit
    db.commit = db.flush  # a teszt-tranzakció a végén rollback
    try:
        c = TestClient(app)
        r = c.patch(f"/api/v1/admin-agent/memory/{m.id}", json={"ervenyes": True})
        assert r.status_code == 409
        r = c.post("/api/v1/admin-agent/memory/bulk", json={"ids": [m.id], "muvelet": "jovahagy"})
        assert r.status_code == 200 and r.json()["kihagyva"] == 1
        assert m.ervenyes is False
        lista = c.get("/api/v1/admin-agent/memory").json()["elemek"]
        assert all(e["id"] != m.id for e in lista)
    finally:
        db.commit = orig_commit
        app.dependency_overrides.clear()
