"""Lara — önellenőrzés a papírozáson (eseti szerződések, TIG-ek, Utókövetés).

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
VALÓDI MODELLHÍVÁS NINCS.

Fedi: a kihagyott TIG-re Lara kérdez (alapból azt várja, hogy kell); a
„mindig így" válaszból partnerre szabott papír-szabály lesz, és a következő
önellenőrzésen már eltalálja; a tételek összegétől eltérő nettó összegre is
kérdez; a vak jóslat nem használja az adott rekord saját tanulságát; a tervező
a papír-tudásból előtölti a hiányzó tárgyat / ÁFA-jelzőt.
"""

from __future__ import annotations

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


def _tig(db, ceg, *, allapot="Kiküldve", netto=None, tetelek=(), **mezok):
    from app.models.employee import Employee, EmployeeType
    from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
    from app.models.project import Project

    t = PerformanceCertificate(ceg_neve=ceg, allapot=allapot, netto_osszeg=netto, **mezok)
    db.add(t)
    db.flush()
    if tetelek:
        e = Employee(full_name=f"Papír Teszt {t.id}", tipus=EmployeeType.KULSOS)
        db.add(e)
        for i, n in enumerate(tetelek):
            p = Project(nev=f"Papír-teszt projekt {t.id}/{i}")
            db.add(p)
            db.flush()
            db.add(PerformanceCertificateTetel(certificate_id=t.id, project_id=p.id, employee_id=e.id, netto_osszeg=n))
        db.flush()
        db.refresh(t)
    return t


def _jovahagyott_megfigyeles(db, tig):
    from app.models.admin_agent import MemoryChunk

    db.add(MemoryChunk(hatokor="tig", tartalom=f"TIG #{tig.id}", forras=f"megfigyeles:tig:{tig.id}",
                       minosites="jovahagyott", tanulasi_halmaz="jovahagyott", ervenyes=True, regi_korszak=False))
    db.flush()


def _kerdes(db, kulcs):
    from app.models.admin_agent import LaraKerdes

    return db.scalars(select(LaraKerdes).where(LaraKerdes.kulcs == kulcs)).all()


def test_kihagyott_tig_kerdez_mindig_valasz_utan_eltalalja(db):
    from app.admin_agent.memory import partner_kulcs
    from app.admin_agent.onellenorzes import onellenorzes, valaszol
    from app.admin_agent.onellenorzes_papir import PapirTudas

    ceg = "Kihagyó Papírteszt Stúdió Kft."
    for _ in range(2):
        _tig(db, ceg, allapot="Kihagyva", kihagyas_oka="Havidíjas, nem kell TIG")
    kulcs = partner_kulcs(ceg)

    elso = onellenorzes(db)
    db.flush()
    kerdesek = _kerdes(db, f"papir:tig:kihagyas:{kulcs}")
    assert len(kerdesek) == 1
    k = kerdesek[0]
    assert k.tipus == "papir" and len(k.kontextus["esetek"]) == 2
    assert "kihagytátok" in k.kerdes and "Havidíjas" in k.kerdes
    assert elso["teruletek"]["tig"]["elter"] >= 2

    # Ismételt futás: nincs duplikált kérdés.
    onellenorzes(db)
    db.flush()
    assert len(_kerdes(db, f"papir:tig:kihagyas:{kulcs}")) == 1

    e = valaszol(db, k, valasz_tipus="mindig", magyarazat="Havidíjas partner.", user_id=2, elesithet=True)
    assert e["szabaly_allapot"] == "active" and e["pelda_id"]
    j = PapirTudas(db).josol("tig", kulcs, "kihagyas")
    assert j[0] is True and "élesített szabály" in j[1]

    # Egy ÚJ kihagyott TIG-et már eltalál (nincs újabb kérdés).
    _tig(db, ceg, allapot="Kihagyva")
    masodik = onellenorzes(db)
    assert masodik["teruletek"]["tig"]["egyezik"] - elso["teruletek"]["tig"]["egyezik"] >= 3
    assert len(_kerdes(db, f"papir:tig:kihagyas:{kulcs}")) == 1


def test_osszeg_eltérés_a_tetelektol_kerdez(db):
    from app.admin_agent.memory import partner_kulcs
    from app.admin_agent.onellenorzes import onellenorzes, valaszol
    from app.models.admin_agent import PlaybookRule

    ceg = "Összegeltérő Papírteszt Bt."
    _tig(db, ceg, netto=20000, tetelek=(10000, 5000))
    kulcs = partner_kulcs(ceg)
    onellenorzes(db)
    db.flush()
    k = _kerdes(db, f"papir:tig:osszeg:{kulcs}")[0]
    assert "15 000 Ft" in k.kerdes and "20 000 Ft" in k.kerdes
    # Számla kell (alapértelmezés) és el is készült → erre nem kérdez.
    assert not _kerdes(db, f"papir:tig:szamla_kihagyas:{kulcs}")

    e = valaszol(db, k, valasz_tipus="mindig", magyarazat=None, user_id=2, elesithet=False)
    r = db.get(PlaybookRule, e["szabaly_id"])
    assert r.allapot == "pending" and r.hatokor == "tig"
    assert r.feltetelek["mezo"] == "osszeg" and r.feltetelek["ertek"] is True


def test_hibas_papir_valasz_nem_tanit(db):
    from app.admin_agent.memory import partner_kulcs
    from app.admin_agent.onellenorzes import onellenorzes, valaszol

    ceg = "Hibás Papírteszt Kft."
    _tig(db, ceg, allapot="Kihagyva")
    kulcs = partner_kulcs(ceg)
    onellenorzes(db)
    db.flush()
    k = _kerdes(db, f"papir:tig:kihagyas:{kulcs}")[0]
    e = valaszol(db, k, valasz_tipus="hibas", magyarazat=None, user_id=2, elesithet=True)
    assert {k: e[k] for k in ("szabaly_id", "szabaly_allapot", "pelda_id")} == {
        "szabaly_id": None, "szabaly_allapot": None, "pelda_id": None}
    # A hiba javítási feladatot készít, megoldási lépésekkel.
    from app.models.admin_agent import AdminTask

    t = db.get(AdminTask, e["feladat_id"])
    assert t.altipus == "javitas" and t.forras_referenciak["lara_megoldas"]["alap"]
    ujra = onellenorzes(db)
    assert ujra["teruletek"]["tig"]["megmagyarazva"] >= 1


def test_vak_josolat_es_tervezo_elotoltes(db):
    from app.admin_agent.memory import partner_kulcs
    from app.admin_agent.onellenorzes_papir import PapirTudas
    from app.admin_agent.tervezo import _papir_tudas_alkalmazasa

    ceg = "Tárgytanuló Papírteszt Kft."
    t1 = _tig(db, ceg, megbizas_targya="Operatőri munka forgatáson", plusz_afa=True)
    t2 = _tig(db, ceg, megbizas_targya="Operatőri munka forgatáson", plusz_afa=True)
    for t in (t1, t2):
        _jovahagyott_megfigyeles(db, t)
    kulcs = partner_kulcs(ceg)

    tudas = PapirTudas(db)
    assert tudas.josol("tig", kulcs, "targy")[0] == "Operatőri munka forgatáson"
    # Önmagát kivéve csak egy eset marad → tárgyra nem jósol (nincs alapértelmezés).
    assert tudas.josol("tig", kulcs, "targy", kiveve=f"tig:{t1.id}") is None

    mezok, forras = {"ceg_neve": ceg}, {}
    figy = _papir_tudas_alkalmazasa(tudas, "tig", {"nev": "Teszt Elek"}, mezok, forras)
    assert mezok["megbizas_targya"] == "Operatőri munka forgatáson" and mezok["plusz_afa"] is True
    assert forras["megbizas_targya"].startswith("Lara tudása (2 jóváhagyott korábbi eset")
    assert figy == []  # nincs szokásos kihagyás / eltérés

    # A már kitöltött mezőt nem írja felül.
    mezok2 = {"ceg_neve": ceg, "megbizas_targya": "Vágás"}
    _papir_tudas_alkalmazasa(tudas, "tig", {"nev": "Teszt Elek"}, mezok2, {})
    assert mezok2["megbizas_targya"] == "Vágás"
