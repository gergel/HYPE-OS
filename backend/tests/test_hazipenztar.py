"""Házipénztár: a négy fajta tétel és az ATM-átvezetés kiadás nélkül.

- BEVÉTEL: csak készpénzes (projektkód-)kifizetés;
- ÁTVEZETÉS: ATM-felvétel - a házipénztár nő, kiadás-sor NEM keletkezik;
- SIMA KIADÁS: készpénzes kiadás, ami mellé van/lesz számla;
- FEKETE KIADÁS: készpénzes kiadás „nem lesz számla” jelöléssel.

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
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


def test_negy_fajta_es_egyenleg(db):
    from app.models.finance import Expense, KpForgalom, Revenue
    from app.models.project_code import ProjectCode
    from app.services import kassza

    elotte = kassza.kep(db).osszes
    pk = ProjectCode(projektkod="HAZIP-TESZT (demó)")
    db.add(pk)
    db.flush()
    nap = date(2026, 5, 4)
    db.add_all([
        Revenue(project_code_id=pk.id, netto=100_000, brutto=127_000, fizetes_datuma=nap, fizetes_modja="Készpénz"),
        # Utalt bevétel: nem a házipénztáré.
        Revenue(project_code_id=pk.id, netto=500_000, fizetes_datuma=nap, fizetes_modja="Átutalás"),
        KpForgalom(kiadas_datuma=nap, osszeg=200_000, megnevezes="KP felvétel ATM (demó)"),
        Expense(megnevezes="Taxi (demó)", netto=10_000, brutto=12_700, fizetes_datuma=nap, kesz=True,
                kifizetes_modja="Készpénz"),
        Expense(megnevezes="Borravaló (demó)", netto=5_000, fizetes_datuma=nap, kesz=True,
                kifizetes_modja="Készpénz", nincs_szamla=True),
        # Még ki nem fizetett készpénzes kiadás: nem mozdult a dobozból.
        Expense(megnevezes="Függő (demó)", netto=9_999, fizetes_datuma=nap, kesz=False, kifizetes_modja="Készpénz"),
    ])
    db.flush()

    kep = kassza.kep(db)
    o = kep.osszes
    assert o.bevetel - elotte.bevetel == pytest.approx(127_000)
    assert o.atvezetes - elotte.atvezetes == pytest.approx(200_000)
    assert o.sima_kiadas - elotte.sima_kiadas == pytest.approx(12_700)
    assert o.fekete_kiadas - elotte.fekete_kiadas == pytest.approx(5_000)
    assert o.egyenleg - elotte.egyenleg == pytest.approx(127_000 + 200_000 - 12_700 - 5_000)
    tipusok = {s.megnevezes: s.tipus for s in kep.sorok if "(demó)" in s.megnevezes}
    assert tipusok["Taxi (demó)"] == kassza.SIMA_KIADAS
    assert tipusok["Borravaló (demó)"] == kassza.FEKETE_KIADAS
    assert tipusok["KP felvétel ATM (demó)"] == kassza.ATVEZETES
    assert "Függő (demó)" not in tipusok


def test_atm_atvezetes_nem_csinal_kiadast(db):
    from app.api.routes.finance import _kp_forgalom_before_create
    from app.models.finance import Expense

    elotte = db.scalar(select(func.count()).select_from(Expense))
    adat = _kp_forgalom_before_create(
        {"megnevezes": "KP felvétel ATM (demó)", "osszeg": 150_000, "kiadas_datuma": date(2026, 6, 1)}, db
    )
    db.flush()
    assert db.scalar(select(func.count()).select_from(Expense)) == elotte
    assert adat["forgalom"] == "atvezetes" and not adat.get("expense_id")


def test_nullazas_mindent_kp_torol_ment_es_visszaallit(db, monkeypatch):
    from app.models.document_attachment import DocumentAttachment
    from app.models.finance import Expense, KpForgalom, Revenue
    from app.models.performance_certificate import PerformanceCertificate
    from app.models.project_code import ProjectCode
    from app.services import document_storage, hazipenztar_nullazas, kassza

    # A tárhely ne legyen valódi: a mentés feltöltését rögzítjük.
    feltoltve: dict = {}
    monkeypatch.setattr(document_storage, "is_configured", lambda: True)
    monkeypatch.setattr(document_storage, "upload_bytes", lambda data, key, ct: feltoltve.setdefault(key, data))

    pk = ProjectCode(projektkod="HAZIP-NULL (demó)")
    db.add(pk)
    db.flush()
    kp_bevetel = Revenue(project_code_id=pk.id, netto=80_000, fizetes_datuma=date(2026, 4, 1), fizetes_modja="Készpénz")
    utalt_bevetel = Revenue(project_code_id=pk.id, netto=90_000, fizetes_datuma=date(2026, 4, 1),
                            fizetes_modja="Átutalás")
    kp_kiadas = Expense(megnevezes="KP kiadás (demó)", netto=7_000, kesz=True, kifizetes_modja="kp",
                        fizetes_datuma=date(2025, 3, 3))
    atm_kiadas = Expense(megnevezes="KP felvétel (demó)", netto=100_000, kifizetes_modja="Bankkártya",
                         kiadas_leiras=hazipenztar_nullazas.ATM_KIADAS_LEIRAS)
    utalt_kiadas = Expense(megnevezes="Utalt (demó)", netto=5_000, kesz=True, kifizetes_modja="Átutalás")
    db.add_all([kp_bevetel, utalt_bevetel, kp_kiadas, atm_kiadas, utalt_kiadas])
    db.flush()
    atm = KpForgalom(kiadas_datuma=date(2024, 1, 1), osszeg=100_000, megnevezes="KP felvétel (demó)",
                     expense_id=atm_kiadas.id)
    tig = PerformanceCertificate(expense_id=kp_kiadas.id, szamla_kifizetve=True)
    szamla = DocumentAttachment(entity_type="projectCode", entity_id=pk.id, kategoria="szamla",
                                filename="s.pdf", storage_key="teszt/s", url="https://x/s",
                                revenue_id=kp_bevetel.id, kifizetve_datuma=date(2026, 4, 1))
    bizonylat = DocumentAttachment(entity_type="expense", entity_id=kp_kiadas.id, kategoria="szamla",
                                   filename="b.pdf", storage_key="teszt/b", url="https://x/b")
    db.add_all([atm, tig, szamla, bizonylat])
    db.flush()
    ids = {"kp_bevetel": kp_bevetel.id, "kp_kiadas": kp_kiadas.id, "atm_kiadas": atm_kiadas.id, "atm": atm.id,
           "bizonylat": bizonylat.id}

    elonezet = hazipenztar_nullazas.elonezet(db)
    assert elonezet["kiadas_db"] >= 2 and elonezet["bevetel_db"] >= 1 and elonezet["kp_forgalom_db"] >= 1

    eredmeny = hazipenztar_nullazas.vegrehajt(db)
    db.flush()
    db.expire_all()

    # Törölve: minden KP tétel, a régi ATM-hez gyártott kiadás is.
    assert db.get(Revenue, ids["kp_bevetel"]) is None
    assert db.get(Expense, ids["kp_kiadas"]) is None
    assert db.get(Expense, ids["atm_kiadas"]) is None
    assert db.get(KpForgalom, ids["atm"]) is None
    assert db.get(DocumentAttachment, ids["bizonylat"]) is None
    # Megmaradt: a nem készpénzes tételek.
    assert db.get(Revenue, utalt_bevetel.id) is not None
    assert db.get(Expense, utalt_kiadas.id) is not None
    # Visszaállt: a TIG újra kifizetetlen, a megrendelői számla nem „Kifizetve”.
    assert tig.expense_id is None and tig.szamla_kifizetve is False
    assert szamla.revenue_id is None and szamla.kifizetve_datuma is None
    # A házipénztár üres.
    kep = kassza.kep(db)
    assert kep.sorok == [] and kep.egyenleg == 0
    # A mentés tartalmazza a törölteket, és fel is töltődött.
    mentes = eredmeny["mentes"]
    assert ids["kp_bevetel"] in {r["id"] for r in mentes["bevetelek"]}
    assert ids["kp_kiadas"] in {r["id"] for r in mentes["kiadasok"]}
    assert ids["bizonylat"] in {r["id"] for r in mentes["csatolmanyok"]}
    assert eredmeny["mentes_kulcs"] in feltoltve


def test_nullazas_vegpont_megerosites_nelkul_nem_fut(db):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    fej = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
    r = TestClient(app).post("/api/v1/finance/hazipenztar/nullazas", json={"megerosites": "igen"}, headers=fej)
    assert r.status_code == 400
    r = TestClient(app).get("/api/v1/finance/hazipenztar/nullazas", headers=fej)
    assert r.status_code == 200 and r.json()["megerosites"] == "NULLÁZÁS"
