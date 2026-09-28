"""A jóváhagyásra váró javaslat emberi nyelvű leírása: nevek az azonosítók
helyett, pontosan az, ami a végrehajtáskor történik. Rollbackes DB-teszt."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent.javaslat_leiras import email_leiras, szamla_leiras
from app.models.admin_agent import AdminTask


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


def _alap(db):
    from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, BejovoSzamla
    from app.models.performance_certificate import PerformanceCertificate
    from app.models.project_code import ProjectCode

    pc = ProjectCode(projektkod="LEIRAS-TESZT-1")
    db.add(pc)
    db.flush()
    cert = PerformanceCertificate(project_code_id=pc.id, ceg_neve="Bodor (demó) Bt.", teljesites_szoveg="2026. szeptember",
                                  netto_osszeg=110000)
    db.add(cert)
    db.flush()
    b = BejovoSzamla(allapot=ALLAPOT_ELLENORZENDO, kibocsato_nev="Bodor (demó) Bt.", szamlaszam="DEMO-2026-7",
                     netto=110000, brutto=110000, penznem="HUF", cel_certificate_id=cert.id)
    db.add(b)
    db.flush()
    t = AdminTask(tipus="szamla", cim="Számla: Bodor (demó) Bt.", forras_referenciak={"bejovo_szamla_id": b.id})
    return pc, cert, b, t


def test_kulsos_tig_nevvel_es_mi_nem_tortenik(db):
    pc, _, b, t = _alap(db)
    payload = {"netto": 110000, "brutto": 110000, "penznem": "HUF", "cel_tipus": "kulsos_tig",
               "cel_project_code_id": pc.id}
    le = szamla_leiras(db, payload, t)
    assert le["cim"] == "A(z) Bodor (demó) Bt. számlája (DEMO-2026-7)"
    assert "110 000 Ft" in le["reszletek"][0]
    szoveg = " ".join(le["lepesek"])
    assert "Bodor (demó) Bt. külsős TIG-jéhez kerül" in szoveg and "Projekt: LEIRAS-TESZT-1" in szoveg
    assert "Teljesítés: 2026. szeptember" in szoveg
    assert "Új kiadás NEM jön létre" in szoveg
    assert any("Utalás nem indul" in x for x in le["nem_tortenik"])
    assert le["figyelmeztetesek"] == [] and le["link"] == f"/penzugyek/bejovo-szamlak?id={b.id}"
    assert "cel_project_code_id" not in str(le) and "796" not in str(le)


def test_uj_kiadas_projektkoddal_nem_kifizetett(db):
    pc, _, _, t = _alap(db)
    le = szamla_leiras(db, {"netto": 50000, "cel_tipus": "kiadas_uj", "cel_project_code_id": pc.id}, t)
    szoveg = " ".join(le["lepesek"])
    assert "Új kiadás jön létre" in szoveg and "LEIRAS-TESZT-1" in szoveg and "NEM kifizetettként" in szoveg


def test_hianyzo_cel_figyelmeztet(db):
    _, _, b, t = _alap(db)
    b.cel_certificate_id = None
    db.flush()
    le = szamla_leiras(db, {"cel_tipus": "kulsos_tig"}, t)
    assert le["figyelmeztetesek"] and "hibára futna" in le["figyelmeztetesek"][0]
    assert szamla_leiras(db, {"cel_tipus": "egyeb"}, t)["figyelmeztetesek"]


def test_email_leiras():
    le = email_leiras({"to": ["konyvelo@example.com"], "subject": "Számla (demó)", "html_body": "<p>Szia, <b>küldöm</b>.</p>"})
    assert "konyvelo@example.com" in le["cim"] and "Tárgy: Számla (demó)." in le["reszletek"]
    assert "Szia, küldöm ." in " ".join(le["lepesek"]) or "Szia, küldöm." in " ".join(le["lepesek"])
    assert email_leiras({})["figyelmeztetesek"]
