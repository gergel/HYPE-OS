"""Lara — a teljes rendszer figyelése (csak tanulás) és a hatáskör (csak
adminisztráció).

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback."""

from __future__ import annotations

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from app.admin_agent.rendszer import rendszer_figyeles
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


def _projekt(db):
    from datetime import date

    from app.models.finance import Expense
    from app.models.project import Project
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod="RSZ-TESZT-1", megrendelo_neve="Rendszerteszt Zrt.", project_nev="Rendszerteszt film",
                     datum=date.today())
    db.add(pc)
    db.flush()
    db.add(Project(nev="Rendszerteszt forgatás", project_code_id=pc.id))
    db.add(Expense(megnevezes="Rendszerteszt Kft.", netto=1000, brutto=1270, kesz=True, project_code_id=pc.id))
    db.flush()
    return pc


def test_csak_lara_sajat_tablaiba_ir(db):
    """Az üzleti táblákba semmit nem ír: minden új/módosított objektum aa_ tábla."""
    _projekt(db)
    db.flush()
    irt: set[str] = set()

    @event.listens_for(db, "before_flush")
    def _figyel(session, _ctx, _inst):
        for o in list(session.new) + list(session.dirty):
            irt.add(o.__table__.name)

    try:
        r = rendszer_figyeles(db, kenyszeritett=True)
        db.flush()
    finally:
        event.remove(db, "before_flush", _figyel)
    assert r["figyelt_tabla"] > 50
    assert irt and all(t.startswith("aa_") for t in irt), irt


def test_projektkod_eletut_es_modul_ismeret(db):
    from app.admin_agent.memory import kapcsolodo_tudas

    pc = _projekt(db)
    rendszer_figyeles(db, kenyszeritett=True)
    db.flush()
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"rendszer:projektkod:{pc.id}"))
    assert m is not None and m.ervenyes and m.hatokor == "rendszer"
    assert "RSZ-TESZT-1" in m.tartalom and "Kiadások: 1" in m.tartalom and "Forgatások" in m.tartalom
    modul = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == "rendszer:modul:expenses"))
    assert modul is not None and "Kiadások" in modul.tartalom
    # A tervezetek / elemzés megkapja a projektkód életútját.
    t = kapcsolodo_tudas(db, hatokor="tig", partner="X", project_code_id=pc.id)
    assert t["projekt_eletut"] == m.tartalom


def test_szemelyes_adat_nem_kerul_a_tudasba(db):
    """Munkatársi adatlap kimarad; e-mail/telefon-jellegű mező soha nem kerül ki."""
    from app.models.client import Client, Contact
    from app.models.employee import Employee, EmployeeType

    db.add(Employee(full_name="Titkos Munkatárs", tipus=EmployeeType.BELSOS, email="titkos.munkatars@example.com"))
    c = Client(nev="Titkos Ügyfél Kft.")
    db.add(c)
    db.flush()
    db.add(Contact(client_id=c.id, full_name="Titkos Kapcsolat", email="titkos.kontakt@example.com"))
    db.flush()
    rendszer_figyeles(db, kenyszeritett=True)
    db.flush()
    for m in db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("rendszer:%"))).all():
        assert "titkos.munkatars@example.com" not in m.tartalom
        assert "titkos.kontakt@example.com" not in m.tartalom
        assert "Titkos Munkatárs" not in m.tartalom
    assert db.scalar(select(MemoryChunk).where(MemoryChunk.forras == "rendszer:modul:employees")) is None


def test_kikapcsolva_nem_fut_es_elvetett_tenyt_nem_irja_vissza(db):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.engedett_forrasok = {**(s.engedett_forrasok or {}), "rendszer": False}
    db.flush()
    assert rendszer_figyeles(db)["allapot"] == "kikapcsolva"
    pc = _projekt(db)
    rendszer_figyeles(db, kenyszeritett=True)
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"rendszer:projektkod:{pc.id}"))
    m.visszavont = True
    m.ervenyes = False
    m.tartalom = "elvetve"
    db.flush()
    rendszer_figyeles(db, kenyszeritett=True)
    assert m.tartalom == "elvetve" and m.visszavont


def test_hataskor_csak_adminisztracio(db):
    """Minden eszköz adminisztratív; nem adminisztratív feladatra a végrehajtó
    blokkol; a heti értékelés hatáskör-esetei átmennek."""
    from app.admin_agent.enums import ADMIN_FELADATTIPUSOK
    from app.admin_agent.evals import run_eval, safety_esetek_magveto
    from app.admin_agent.executor import TOOL_REGISTRY, execute_approved
    from app.admin_agent.proposals import _hash
    from app.models.admin_agent import ActionProposal, AdminTask, Approval
    from app.models.employee import Employee

    assert all(spec.tipus in ADMIN_FELADATTIPUSOK for spec in TOOL_REGISTRY.values())
    assert ADMIN_FELADATTIPUSOK == {"szamla", "email", "tig", "szerzodes", "egyeb"}

    t = AdminTask(tipus="diszpo", cim="Nem adminisztratív", allapot="awaiting_approval", trust_level="L0")
    db.add(t)
    db.flush()
    payload = {"cel_tipus": "mukodesi"}
    p = ActionProposal(task_id=t.id, eszkoz="szamla_erkeztetes.jovahagy", payload=payload, payload_hash=_hash(payload),
                       allapot="ready", kockazat="R2")
    db.add(p)
    db.flush()
    a = Approval(proposal_id=p.id, payload_hash=p.payload_hash, allapot="approved")
    db.add(a)
    db.flush()
    emp = db.scalars(select(Employee).limit(1)).first()
    if emp is None:
        pytest.skip("Nincs munkatárs a teszthez.")
    ex = execute_approved(db, a, approver=emp)
    assert ex.allapot == "failed" and "adminisztrációs" in ex.eredmeny["blokk_ok"]

    safety_esetek_magveto(db)
    run = run_eval(db)
    hataskor = [e for e in run.eredmeny["esetek"] if e["nev"].startswith("Hatáskör")]
    assert len(hataskor) == 3 and all(e["sikeres"] and not e["kritikus"] for e in hataskor)


def test_idozona_nelkuli_tabla_nem_dont_el(db):
    """Éles hiba („Váratlan szerverhiba"): az `ajanlatkeresek` updated_at
    oszlopa időzóna NÉLKÜLI, a többi időzónás — egy projektkódnál mindkettő
    mozgása az összehasonlításnál TypeError-t dobott. Most normalizálva."""
    from app.models.munkafelajanlas import Ajanlatkeres
    from app.models.project import Project

    pc = _projekt(db)
    proj = db.scalar(select(Project).where(Project.project_code_id == pc.id))
    from datetime import datetime

    # Módosított sor: az oszlop időzóna nélküli, az érték naiv (UTC).
    db.add(Ajanlatkeres(project_id=proj.id, projekt_nev="Rendszerteszt forgatás", munkakor="Operatőr",
                        updated_at=datetime.utcnow()))
    db.flush()
    r = rendszer_figyeles(db, kenyszeritett=True)
    assert r["projektkod"] >= 1
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"rendszer:projektkod:{pc.id}"))
    assert "Ajánlatkérések: 1" in m.tartalom
