"""Az eszköz munka-statisztikája (services/eszkoz_statisztika.py) és az új
eszköz rendszerbe kerülési dátuma.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.api.routes.equipment import _rendszerbe_kerules, _statisztika_kimenet
from app.core.database import engine
from app.models.equipment import Assignment, Equipment
from app.models.eszkoz_kivitel import EszkozKivitel, EszkozKivitelTetel
from app.models.project import Project
from app.services import eszkoz_statisztika

MA = date(2026, 10, 2)


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


def _projekt(db, nev, tol, ig=None, helyszin=None) -> Project:
    p = Project(nev=f"{nev} (demó)", forgatas_datuma=tol, forgatas_datuma_vege=ig, helyszin=helyszin)
    db.add(p)
    db.flush()
    return p


def _eszkoz(db) -> Equipment:
    e = Equipment(nev="Kamera (demó)")
    db.add(e)
    db.flush()
    return e


def test_napok_forgatasonkent_es_atfedes_egy_nap(db):
    e = _eszkoz(db)
    # 3 napos forgatás + egy egynapos ugyanazon a napon (= 1 nap) + egy jövőbeli.
    harom = _projekt(db, "Fesztivál", date(2026, 9, 10), date(2026, 9, 12), "Kapolcs")
    ugyanaz = _projekt(db, "Interjú", date(2026, 9, 12))
    jovo = _projekt(db, "Jövő", date(2026, 12, 1))
    for p in (harom, ugyanaz, jovo):
        db.add(Assignment(equipment_id=e.id, project_id=p.id, qty=1))
    db.flush()

    stat = eszkoz_statisztika.statisztikak(db, [e.id], ma=MA)[e.id]
    assert stat.napok_szama == 3  # 09.10-11-12, a 12-e egyszer
    assert {f.project_id for f in stat.forgatasok} == {harom.id, ugyanaz.id}
    assert all(f.forras == eszkoz_statisztika.FORRAS_FOGLALAS for f in stat.forgatasok)
    # Mindkettő 09.12-én ért véget - az utolsó a később kezdődő.
    assert stat.ahol_utoljara_volt == "Interjú (demó) · 2026.09.12."
    assert stat.forgatasok[-1].nev == "Fesztivál (demó)" and stat.forgatasok[-1].vege == date(2026, 9, 12)


def test_folyamatban_levo_forgatas_csak_maig_szamit(db):
    e = _eszkoz(db)
    p = _projekt(db, "Hosszú", date(2026, 9, 30), date(2026, 10, 5))
    db.add(Assignment(equipment_id=e.id, project_id=p.id, qty=1))
    db.flush()
    assert eszkoz_statisztika.statisztikak(db, [e.id], ma=MA)[e.id].napok_szama == 3  # 09.30, 10.01, 10.02


def test_eszkozkivitel_felulirja_a_foglalast(db):
    e = _eszkoz(db)
    masik = _eszkoz(db)
    p = _projekt(db, "Kivitt", date(2026, 9, 20), date(2026, 9, 21), "Tata")
    # Mindkettő foglalva - de a kivitel szerint csak az első ment ki.
    db.add_all([
        Assignment(equipment_id=e.id, project_id=p.id, qty=1),
        Assignment(equipment_id=masik.id, project_id=p.id, qty=1),
    ])
    k = EszkozKivitel(
        project_id=p.id,
        kod="T99901",
        allapot="lezart",
        kivitel_lezarva_at=datetime(2026, 9, 19, 18, 0, tzinfo=timezone.utc),
        vissza_lezarva_at=datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc),
    )
    db.add(k)
    db.flush()
    db.add_all([
        EszkozKivitelTetel(kivitel_id=k.id, equipment_id=e.id, kivitt_db=1, visszahozott_db=1),
        EszkozKivitelTetel(kivitel_id=k.id, equipment_id=masik.id, kivitt_db=0, visszahozott_db=0),
    ])
    db.flush()

    stat = eszkoz_statisztika.statisztikak(db, [e.id, masik.id], ma=MA)
    # A kint töltött napok: 09.19-től 09.22-ig = 4 nap.
    assert stat[e.id].napok_szama == 4
    assert stat[e.id].forgatasok[0].forras == eszkoz_statisztika.FORRAS_KIVITEL
    # A foglalt, de ki nem vitt eszköz nem dolgozott.
    assert stat[masik.id].napok_szama == 0


def test_kimenet_es_rendszerbe_kerules(db):
    e = _eszkoz(db)
    e.ahol_utoljara_volt = "Régi raktár (demó)"
    db.flush()
    sor = _statisztika_kimenet([{"id": e.id, "ahol_utoljara_volt": "Régi raktár (demó)"}], db, None)[0]
    # Forgatás nélkül: 0 nap, és a régi szöveg megmarad.
    assert (sor["hany_napot_dolgozott"], sor["hany_forgatason_vett_reszt"]) == (0.0, "0")
    assert sor["ahol_utoljara_volt"] == "Régi raktár (demó)"

    data = _rendszerbe_kerules({"nev": "Új (demó)"}, db)
    assert isinstance(data["rendszerbe_kerules_idopontja"], datetime)
    kezi = datetime(2020, 1, 1)
    assert _rendszerbe_kerules({"rendszerbe_kerules_idopontja": kezi}, db)["rendszerbe_kerules_idopontja"] == kezi
