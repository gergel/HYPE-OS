"""HYRON — megfigyelő (projektkód/utókövetés) és tudás-példa jóváhagyás.

Postgres-integráció, DB nélkül self-skip. A megfigyelő-tesztek EGY tranzakcióban
futnak és a végén rollback — semmi nem marad az adatbázisban.

Fedi: a megfigyelés engedélyhez kötött; idempotens (ugyanaz a verzió egyszer);
a lezárt emberi munkából példa-JELÖLT lesz (nem éles); üzleti rekord nem
változik; a példa csak kifejezett jóváhagyással lesz éles, elvetett nem hagyható jóvá.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.observer import megfigyeles
from app.models.admin_agent import ActionTrace, MemoryChunk, SourceEvent
from app.models.finance import Expense


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


def test_megfigyeles_kikapcsolva_nem_csinal_semmit(db):
    """Engedély nélkül (és nem kézi, kényszerített futásként) nincs megfigyelés."""
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.engedett_forrasok = {}
    db.flush()
    r = megfigyeles(db)
    assert r["engedelyezve"] is False
    assert r["uj_megfigyeles"] == 0


def test_megfigyeles_idempotens_es_pelda_jelolt(db):
    """Egy kifizetett (lezárt) kiadásból: 1 forrásesemény + 1 emberi nyomvonal +
    1 példa-JELÖLT (nem érvényes). Újrafuttatva nincs dupla. Az üzleti rekord nem
    változik. Minden egy tranzakcióban → a végén rollback."""
    exp = Expense(megnevezes="Megfigyelő Teszt Kft.", netto=10000, brutto=12700, kesz=True)
    db.add(exp)
    db.flush()
    elotte = (exp.megnevezes, exp.kesz, float(exp.netto))

    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()

    azon = f"kiadas:{exp.id}"
    assert db.query(SourceEvent).filter_by(forras="megfigyeles", forras_azonosito=azon).count() == 1
    assert db.query(ActionTrace).filter_by(eroforras=azon, szereplo="human").count() == 1
    pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"megfigyeles:{azon}"))
    assert pelda is not None
    assert pelda.ervenyes is False  # jelölt — éles döntésben NEM használható
    assert pelda.hatokor == "szamla"

    # Idempotencia: ugyanaz a verzió nem kerül be még egyszer.
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()
    assert db.query(SourceEvent).filter_by(forras="megfigyeles", forras_azonosito=azon).count() == 1
    assert db.query(MemoryChunk).filter(MemoryChunk.forras == f"megfigyeles:{azon}").count() == 1

    # Üzleti rekord változatlan.
    db.refresh(exp)
    assert (exp.megnevezes, exp.kesz, float(exp.netto)) == elotte


def test_nyitott_kiadasbol_nincs_pelda(db):
    """A még nem kifizetett (nem lezárt) kiadás megfigyelés, de NEM példa."""
    exp = Expense(megnevezes="Nyitott Teszt Kft.", netto=5000, brutto=6350, kesz=False)
    db.add(exp)
    db.flush()
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()
    azon = f"kiadas:{exp.id}"
    assert db.query(SourceEvent).filter_by(forras="megfigyeles", forras_azonosito=azon).count() == 1
    assert db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"megfigyeles:{azon}")) is None


def test_pelda_jovahagyas_es_elvetes_api(db):
    """A példa csak kifejezett jóváhagyással lesz éles; elvetett nem hagyható jóvá."""
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    m = MemoryChunk(hatokor="szamla", tartalom="API teszt példa", forras="teszt:api", ervenyes=False, minosites="jelolt")
    db.add(m)
    db.commit()
    mid = m.id
    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
        r = c.patch(f"/api/v1/admin-agent/memory/{mid}", headers=h, json={"ervenyes": True})
        assert r.status_code == 200 and r.json()["ervenyes"] is True
        r = c.patch(f"/api/v1/admin-agent/memory/{mid}", headers=h, json={"visszavont": True})
        assert r.status_code == 200 and r.json()["ervenyes"] is False and r.json()["visszavont"] is True
        r = c.patch(f"/api/v1/admin-agent/memory/{mid}", headers=h, json={"ervenyes": True})
        assert r.status_code == 409
    finally:
        db.query(MemoryChunk).filter(MemoryChunk.id == mid).delete(synchronize_session=False)
        db.commit()


def test_megtanult_tudas_visszahat_az_elemzesre(db):
    """A JÓVÁHAGYOTT tudás (aktív szabály + ugyanazon partner jóváhagyott korábbi
    esete) bekerül egy új elemzés mellé; a jóvá NEM hagyott jelölt és a más
    partnerhez tartozó eset NEM (nincs irreleváns kitöltés). Rollback a végén."""
    from app.admin_agent.pipeline_szamla import arnyek_elemzes
    from app.models.admin_agent import ActionProposal, PlaybookRule
    from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, BejovoSzamla

    db.add(PlaybookRule(hatokor="szamla", cim="Visszacsatolás teszt-szabály", tartalom="x", allapot="active", verzio=1))
    db.add(MemoryChunk(hatokor="szamla", tartalom="HYPE-T: „Visszacsatolás Kft.” kifizetve", ervenyes=True, minosites="jovahagyott"))
    db.add(MemoryChunk(hatokor="szamla", tartalom="HYPE-T: „Visszacsatolás Kft.” jelölt", ervenyes=False, minosites="jelolt"))
    db.add(MemoryChunk(hatokor="szamla", tartalom="HYPE-T: „Másik Partner Bt.” kifizetve", ervenyes=True, minosites="jovahagyott"))
    b = BejovoSzamla(
        allapot=ALLAPOT_ELLENORZENDO, kibocsato_nev="Visszacsatolás Kft.", szamlaszam="VCS-1",
        netto=1000, brutto=1270, penznem="HUF", cel_tipus="mukodesi", javaslat={"cel_tipus": "mukodesi"},
    )
    db.add(b)
    db.flush()

    t = arnyek_elemzes(db, b, trigger="manual")
    db.flush()
    p = db.scalars(select(ActionProposal).where(ActionProposal.task_id == t.id)).first()
    tudas = p.ellenorzesek["kapcsolodo_tudas"]

    assert any(s["cim"] == "Visszacsatolás teszt-szabály" for s in tudas["szabalyok"])
    esetek = [e["tartalom"] for e in tudas["hasonlo_esetek"]]
    assert any("Visszacsatolás Kft.” kifizetve" in e for e in esetek)
    assert not any("jelölt" in e for e in esetek)  # nem jóváhagyott → nem kerül bele
    assert not any("Másik Partner" in e for e in esetek)  # más partner → nem releváns


# ── Tanulási korszak: csak a tanulás kezdete (alap: 2026-09-01) óta ──────────


def _regi_kiadas(db, nev, **kw):
    """Kifizetett kiadás, ami a tanulás kezdete ELŐTT keletkezett (Notion-korszak)."""
    from datetime import datetime, timezone

    alap = dict(megnevezes=nev, netto=20000, brutto=25400, kesz=True,
                created_at=datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc),
                updated_at=datetime.now(timezone.utc))
    alap.update(kw)
    exp = Expense(**alap)
    db.add(exp)
    db.flush()
    return exp


def _kezdet(db, nap: str | None):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    limitek = dict(s.limitek or {})
    limitek.pop("tanulas_kezdete", None)
    if nap:
        limitek["tanulas_kezdete"] = nap
    s.limitek = limitek
    db.flush()


def test_regi_rekordbol_nem_lesz_uj_jelolt(db):
    """A tanulás kezdete előtt keletkezett (utóbb módosított) rekord megfigyelés
    marad, de NEM lesz belőle példa-jelölt; az új rekordból igen."""
    _kezdet(db, "2026-09-01")
    regi = _regi_kiadas(db, "Régi Korszak Kft.")
    uj = Expense(megnevezes="Új Korszak Kft.", netto=1000, brutto=1270, kesz=True)
    db.add(uj)
    db.flush()

    r = megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()
    assert r["kihagyott_regi"] >= 1
    assert db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"megfigyeles:kiadas:{regi.id}")) is None
    uj_pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"megfigyeles:kiadas:{uj.id}"))
    assert uj_pelda is not None and uj_pelda.regi_korszak is False and uj_pelda.forras_keletkezes is not None


def test_notionbol_importalt_rekord_regi_korszak(db):
    """A Notionből importált rekord akkor is régi korszak, ha a kezdőnap után jött be."""
    from app.models.notion_import import NotionImportMap

    _kezdet(db, "2026-09-01")
    exp = Expense(megnevezes="Notion Import Kft.", netto=1000, brutto=1270, kesz=True)
    db.add(exp)
    db.flush()
    db.add(NotionImportMap(notion_page_id=f"teszt-notion-{exp.id}", entity_type="Expense", entity_id=exp.id))
    db.flush()
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()
    assert db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"megfigyeles:kiadas:{exp.id}")) is None


def test_meglevo_regi_jelolt_felreteve_es_visszahozhato(db):
    """A régi korszak már meglévő jelöltje félre lesz téve (nem törlődik); a
    jóváhagyott régi példa jóváhagyott marad (csak jelölve); ha a kezdőnap
    korábbra kerül, a félretett jelölt visszajön."""
    from app.admin_agent.observer import FELRETEVE, korszak_rendezes

    _kezdet(db, "2026-09-01")
    a = _regi_kiadas(db, "Félretett Kft.")
    b = _regi_kiadas(db, "Jóváhagyott Régi Kft.")
    jelolt = MemoryChunk(hatokor="szamla", tartalom="régi jelölt", forras=f"megfigyeles:kiadas:{a.id}",
                         ervenyes=False, minosites="jelolt")
    jovahagyott = MemoryChunk(hatokor="szamla", tartalom="régi jóváhagyott", forras=f"megfigyeles:kiadas:{b.id}",
                              ervenyes=True, minosites="jovahagyott")
    db.add_all([jelolt, jovahagyott])
    db.flush()

    r = korszak_rendezes(db)
    assert r["felreteve"] >= 1 and r["regi_jovahagyott"] >= 1
    assert jelolt.minosites == FELRETEVE and jelolt.regi_korszak is True and jelolt.visszavont is False
    assert jovahagyott.ervenyes is True and jovahagyott.regi_korszak is True

    _kezdet(db, "2026-08-01")
    r = korszak_rendezes(db)
    assert r["visszahozva"] >= 1
    assert jelolt.minosites == "jelolt" and jelolt.regi_korszak is False


def test_regi_pelda_kisebb_sullyal(db):
    """Ugyanannál a partnernél az új korszak példája ELŐBB jön, a régi utána,
    megjelölve (a modell is kisebb súllyal kezeli)."""
    from app.admin_agent.memory import REGI_ELOTAG, kapcsolodo_tudas

    db.add(MemoryChunk(hatokor="szamla", tartalom="Súlyteszt Kft. régi eset", ervenyes=True,
                       minosites="jovahagyott", regi_korszak=True))
    db.flush()
    db.add(MemoryChunk(hatokor="szamla", tartalom="Súlyteszt Kft. új eset", ervenyes=True,
                       minosites="jovahagyott", regi_korszak=False))
    db.flush()
    esetek = kapcsolodo_tudas(db, hatokor="szamla", partner="Súlyteszt Kft.")["hasonlo_esetek"]
    assert [e["regi"] for e in esetek] == [False, True]
    assert esetek[1]["tartalom"].startswith(REGI_ELOTAG)
    assert not esetek[0]["tartalom"].startswith(REGI_ELOTAG)


def test_tanulas_kezdete_jovobeli_datum_elutasitva():
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
        r = c.patch("/api/v1/admin-agent/settings", headers=h, json={"tanulas_kezdete": "2999-01-01"})
    except OperationalError:
        pytest.skip("Postgres nem elérhető.")
    assert r.status_code == 400
