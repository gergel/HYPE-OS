"""Pénzügy - utalásra váró: egy alvállalkozó számlája csak akkor UTALHATÓ, ha
(1) a megrendelő már kifizette a projektkódot (a "másik oldal" bejött), ÉS
(2) a szerződését aláírva visszaküldte (a felhasználó kérése, 2026-10).

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.contract import Contract, ContractType
from app.models.employee import Employee, EmployeeType
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateInvoice
from app.models.project import Project
from app.models.project_code import ProjectCode


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


def _tig(db, *, project=None, project_code=None, employee) -> PerformanceCertificate:
    t = PerformanceCertificate(project_id=project.id if project else None,
                               project_code_id=project_code.id if project_code else None,
                               employee_id=employee.id, allapot="Kiküldve", netto_osszeg=50000, szamla_kifizetve=False)
    db.add(t)
    db.flush()
    db.add(PerformanceCertificateInvoice(certificate_id=t.id, filename="szamla.pdf", storage_key="k", url="u"))
    db.flush()
    db.refresh(t)
    return t


def _tetel(db, tig):
    from app.api.routes.finance import _utalasra_varo_tetelek

    db.expire_all()
    return next(t for t, _ in _utalasra_varo_tetelek(db) if t.kulcs == f"kulsos_tig:{tig.id}")


@pytest.fixture
def k(db):
    kulsos = Employee(full_name="Utalás Vágó (demó)", tipus=EmployeeType.KULSOS, email="utalas-vago-demo@example.test",
                      is_active=True)
    pk = ProjectCode(projektkod="UTAL-DEMO-1", szamla_statusza="Kifizetve és számla feltöltve")
    db.add_all([kulsos, pk])
    db.flush()
    p = Project(nev="Utalás forgatás (demó)", forgatas_datuma=date(2026, 9, 20), project_code_id=pk.id)
    db.add(p)
    db.flush()
    p.crew.append(kulsos)
    db.flush()
    return {"db": db, "kulsos": kulsos, "pk": pk, "p": p}


def _szerzodes(db, k, allapot, alairva=False, **kw):
    c = Contract(tipus=ContractType.ALVALLALKOZOI, employee_id=k["kulsos"].id, szerzodes_allapota=allapot,
                 alairva=alairva, netto_osszeg=50000, **kw)
    db.add(c)
    db.flush()
    return c


def test_fedezet_megvan_de_alairt_szerzodes_nincs(k):
    db = k["db"]
    c = _szerzodes(db, k, "Kiküldve", project_id=k["p"].id)
    tig = _tig(db, project=k["p"], employee=k["kulsos"])
    t = _tetel(db, tig)
    assert t.fedezettseg == "szerzodes"
    assert t.szerzodes_hiany and "aláírásra vár" in t.szerzodes_hiany[0]
    # Aláírva visszaérkezett -> utalható.
    c.alairva = True
    db.flush()
    t = _tetel(db, tig)
    assert t.fedezettseg == "fedezett" and t.szerzodes_hiany == []


def test_szerzodes_nelkul_nem_utalhato_kihagyva_igen(k):
    db = k["db"]
    tig = _tig(db, project=k["p"], employee=k["kulsos"])
    t = _tetel(db, tig)
    assert t.fedezettseg == "szerzodes" and "Hiányzik" in t.szerzodes_hiany[0]
    _szerzodes(db, k, "Kihagyva", project_id=k["p"].id, kihagyas_oka="A partnercég szerződik vele (demó).")
    assert _tetel(db, tig).fedezettseg == "fedezett"


def test_fedezet_nelkul_marad_fedezetre_var_es_latszik_a_szerzodes_hiany(k):
    db = k["db"]
    k["pk"].szamla_statusza = "Számlázva"
    db.flush()
    tig = _tig(db, project=k["p"], employee=k["kulsos"])
    t = _tetel(db, tig)
    assert t.fedezettseg == "var" and t.szerzodes_hiany


def test_projektkodos_tig(k):
    db = k["db"]
    pk2 = ProjectCode(projektkod="UTAL-DEMO-PK", szamla_statusza="Kifizetve")
    db.add(pk2)
    db.flush()
    tig = _tig(db, project_code=pk2, employee=k["kulsos"])
    assert _tetel(db, tig).fedezettseg == "szerzodes"
    c = _szerzodes(db, k, "Kiküldve", project_code_id=pk2.id)
    assert _tetel(db, tig).fedezettseg == "szerzodes"
    c.alairva = True
    db.flush()
    assert _tetel(db, tig).fedezettseg == "fedezett"
