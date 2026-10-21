"""Strukturált számla-piszkozat, hiányzó dokumentumok utókövetése, audit-napló.

Rollbackes Postgres-teszt: a demó adatok (minden név "(demó)" jelölésű) egy
tranzakcióban jönnek létre, és a végén visszagörgetődnek - a végpontok
`commit`-ja itt `flush`. A tárhelyet memóriabeli helyettesítő adja.

Amit rögzít:
- a bemeneti érvényesítési szabályok (422-es szint);
- partner adószám alapján, keretszerződés a forgatás napján, kiküldött
  külsős TIG projektkód + nap szerint;
- hiányzó szerződés/TIG -> `hianyzo_dokumentumok` + előkészítési opciók,
  amelyek NEM futnak le (nincs új szerződés/TIG/kiadás);
- a jóváhagyás (pénzügyi állapotváltozás) csak explicit, friss ellenőrző
  kóddal megerősítve megy át, és minden lépés az audit-naplóba kerül;
- a /utokovetes/hianyok mátrix és az emlékeztető-rögzítés."""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.models.automatizalas import AutomatizalasAudit, UtokovetesDokumentum
from app.models.bejovo_szamla import (
    ALLAPOT_ELLENORZENDO,
    ALLAPOT_HIANYZO_DOKUMENTUMOK,
    ALLAPOT_JOVAHAGYVA,
    BejovoSzamla,
)
from app.models.contract import Contract, ContractPeriod, ContractType
from app.models.employee import Employee, EmployeeType
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.vallalkozas import Vallalkozas
from app.schemas.szamla_draft import SzamlaDraftIn
from app.services import szamla_draft, utokovetes_hianyok

MA = date.today()


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


@pytest.fixture()
def admin(db):
    e = db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin.")
    return e


@pytest.fixture()
def tarhely(monkeypatch):
    from app.services import document_storage

    tar: dict[str, bytes] = {}
    monkeypatch.setattr(document_storage, "upload_bytes", lambda adat, kulcs, ct: tar.__setitem__(kulcs, adat) or f"mem://{kulcs}")
    monkeypatch.setattr(document_storage, "download_bytes", lambda kulcs: tar[kulcs])
    monkeypatch.setattr(document_storage, "delete_object", lambda kulcs: tar.pop(kulcs, None))
    return tar


def _szabad_adoszam(db) -> str:
    foglalt = {("".join(c for c in (x or "") if c.isdigit()))[:8] for x in db.scalars(select(Vallalkozas.adoszam))}
    foglalt |= {("".join(c for c in (x or "") if c.isdigit()))[:8] for x in db.scalars(select(Employee.vallalkozas_adoszama))}
    while True:
        torzs = str(random.randint(10_000_000, 99_999_999))
        if torzs not in foglalt:
            return f"{torzs}-2-42"


@pytest.fixture()
def kornyezet(db):
    """Egy lezajlott (10 napja volt) forgatás egy külsős stábtaggal, akinek a
    munkáját egy demó vállalkozás számlázza."""
    adoszam = _szabad_adoszam(db)
    v = Vallalkozas(nev="Fénysugár (demó) Kft.", adoszam=adoszam, szekhely="Budapest (demó)")
    ember = Employee(full_name="Világosító (demó) Bence", tipus=EmployeeType.KULSOS)
    kod = f"DEMO{MA.year % 100:02d}-{random.randint(10000, 99999)}"
    pc = ProjectCode(projektkod=kod)
    db.add_all([v, ember, pc])
    db.flush()
    nap = MA - timedelta(days=10)
    p = Project(nev="(demó) Reklámforgatás", project_code_id=pc.id, forgatas_datuma=nap, diszpo="Kiküldve")
    p.crew.append(ember)
    db.add(p)
    db.flush()
    db.add(ProjectSzamlazo(project_id=p.id, employee_id=ember.id, szamlazo_vallalkozas_id=v.id))
    db.flush()
    db.expire_all()
    return {"v": v, "ember": ember, "pc": pc, "p": db.get(Project, p.id), "nap": nap, "adoszam": adoszam}


def _bemenet(k: dict, **tobb) -> SzamlaDraftIn:
    adat = {
        "partner_adoszam": k["adoszam"],
        "partner_nev": "Fénysugár (demó) Kft.",
        "szamlaszam": f"FS-DEMO-{random.randint(1000, 9999)}",
        "netto": "100000",
        "afa_osszeg": "27000",
        "fizetesi_hatarido": (MA + timedelta(days=15)).isoformat(),
        "kiallitas_datuma": MA.isoformat(),
        "projektkod": k["pc"].projektkod.lower(),
        "forgatas_datuma": k["nap"].isoformat(),
    }
    adat.update(tobb)
    return SzamlaDraftIn(**adat)


def _keretszerzodes(db, k) -> Contract:
    c = Contract(tipus=ContractType.ALVALLALKOZOI, vallalkozas_id=k["v"].id, keretszerzodes=True, aktiv=True,
                 ceg_neve=k["v"].nev, adoszam=k["adoszam"])
    c.idoszakok.append(ContractPeriod(kezdet=k["nap"] - timedelta(days=100), veg=None))
    db.add(c)
    db.flush()
    return c


def _tig(db, k, allapot="Kiküldve", netto=100000) -> PerformanceCertificate:
    t = PerformanceCertificate(project_id=k["p"].id, vallalkozas_id=k["v"].id, allapot=allapot, ceg_neve=k["v"].nev,
                               adoszam=k["adoszam"], netto_osszeg=netto, plusz_afa=True)
    t.tetelek.append(PerformanceCertificateTetel(project_id=k["p"].id, employee_id=k["ember"].id))
    db.add(t)
    db.flush()
    return t


def _auditok(db, bejovo_id: int) -> list[AutomatizalasAudit]:
    return list(db.scalars(
        select(AutomatizalasAudit)
        .where(AutomatizalasAudit.eroforras_tipus == "bejovo_szamla", AutomatizalasAudit.eroforras_id == bejovo_id)
        .order_by(AutomatizalasAudit.id)
    ).all())


# ── Bemeneti érvényesítési szabályok ─────────────────────────────────────────


def test_bemeneti_szabalyok():
    alap = {"partner_adoszam": "12345678-2-42", "partner_nev": "Teszt (demó) Kft.", "szamlaszam": "A-1"}
    # A hiányzó harmadik összeg kiszámolódik.
    d = SzamlaDraftIn(**alap, netto="1000", brutto="1270")
    assert d.afa_osszeg == Decimal("270.00")
    # Közösségi adószám és törzsszám is elfogadott, kanonikus alakra hozva.
    assert SzamlaDraftIn(**{**alap, "partner_adoszam": "HU12345678"}, netto=1, afa_osszeg=0).partner_adoszam == "12345678"
    assert SzamlaDraftIn(**{**alap, "partner_adoszam": "12345678242"}, netto=1, afa_osszeg=0).partner_adoszam == "12345678-2-42"
    hibasak = [
        {**alap, "partner_adoszam": "1234", "netto": 1, "afa_osszeg": 0},  # rövid adószám
        {**alap, "partner_adoszam": "12345678-9-42", "netto": 1, "afa_osszeg": 0},  # rossz ÁFA-kód
        {**alap, "netto": 1000},  # csak egy összeg
        {**alap, "netto": 1000, "afa_osszeg": 270, "brutto": 1500},  # nem adják ki egymást
        {**alap, "netto": -5, "afa_osszeg": 0},  # negatív
        {**alap, "szamlaszam": "   ", "netto": 1, "afa_osszeg": 0},  # üres számlaszám
        {**alap, "netto": 1, "afa_osszeg": 0, "kiallitas_datuma": "2026-09-10", "fizetesi_hatarido": "2026-09-01"},
        {**alap, "netto": 1, "afa_osszeg": 0, "projektkod": "ABC;DROP"},  # tiltott karakter
        {**alap, "netto": 1, "afa_osszeg": 0, "penznem": "forint"},
        {**alap, "netto": 1, "afa_osszeg": 0, "mezo_bizonyossag": {"netto": 1.5}},
    ]
    for h in hibasak:
        with pytest.raises(ValidationError):
            SzamlaDraftIn(**h)


# ── Érvényesítés a törzsadattal ──────────────────────────────────────────────


def test_ismeretlen_partner_hianyzo_dokumentumok(db, admin, kornyezet):
    adat = _bemenet(kornyezet, partner_adoszam=_szabad_adoszam(db), partner_nev="Ismeretlen (demó) Bt.")
    b, mar = szamla_draft.letrehoz(db, adat, admin)
    assert not mar and b.forras == "draft" and b.allapot == ALLAPOT_HIANYZO_DOKUMENTUMOK
    hianyzo = {h["dokumentum"] for h in b.validacio["hianyzo"]}
    assert {"partner", "keretszerzodes", "tig"} <= hianyzo
    opciok = {o["kod"]: o for o in b.validacio["elokeszitesi_opciok"]}
    assert opciok["partner_felvetele"]["vegpont"]["utvonal"] == "/api/v1/vallalkozasok"
    assert all(o["automatikusan_fut"] is False for o in opciok.values())
    muveletek = [a.muvelet for a in _auditok(db, b.id)]
    assert muveletek == ["szamla_draft.letrehozas", "szamla_draft.validacio"]


def test_hianyzo_szerzodes_es_tig_opciok_mellekhatas_nelkul(db, admin, kornyezet):
    elotte = (
        db.scalar(select(func.count(Contract.id))),
        db.scalar(select(func.count(PerformanceCertificate.id))),
        db.scalar(select(func.count(Expense.id))),
    )
    b, _ = szamla_draft.letrehoz(db, _bemenet(kornyezet), admin)
    assert b.allapot == ALLAPOT_HIANYZO_DOKUMENTUMOK
    assert b.partner_vallalkozas_id == kornyezet["v"].id and b.szerzodes_id is None
    assert b.hivatkozott_projektkod == kornyezet["pc"].projektkod  # nagybetűsítve
    v = b.validacio
    assert v["ellenorzesek"]["partner"]["egyezes"] == "adoszam"
    assert [p["id"] for p in v["ellenorzesek"]["projekt"]["projektek"]] == [kornyezet["p"].id]
    opciok = {o["kod"]: o for o in v["elokeszitesi_opciok"]}
    kulcs = f"v{kornyezet['v'].id}"
    assert opciok["keretszerzodes_elokeszitese"]["vegpont"]["torzs"] == {"vallalkozas_id": kornyezet["v"].id}
    assert opciok["eseti_szerzodes_elokeszitese"]["vegpont"]["utvonal"] == (
        f"/api/v1/alvallalkozoi-szerzodesek/{kornyezet['p'].id}/{kulcs}/save"
    )
    tig = opciok["tig_elokeszitese"]["vegpont"]
    assert tig["utvonal"] == f"/api/v1/teljesitesi-igazolasok/{kornyezet['p'].id}/{kulcs}/save"
    assert tig["torzs"]["netto_osszeg"] == 100000.0 and tig["torzs"]["teljesites_kezdete"] == kornyezet["nap"].isoformat()
    # Az opciók csak javaslatok: semmi nem jött létre.
    utana = (
        db.scalar(select(func.count(Contract.id))),
        db.scalar(select(func.count(PerformanceCertificate.id))),
        db.scalar(select(func.count(Expense.id))),
    )
    assert utana == elotte
    # Hiányzó dokumentummal nem hagyható jóvá.
    from app.services.szamla_erkeztetes import ErkeztetesHiba, jovahagy

    with pytest.raises(ErkeztetesHiba):
        jovahagy(db, b, admin, {"cel_tipus": "kulsos_tig"})


def test_meglevo_dokumentumokkal_ellenorzendo_es_idempotens(db, admin, kornyezet):
    c = _keretszerzodes(db, kornyezet)
    t = _tig(db, kornyezet, netto=95000)
    adat = _bemenet(kornyezet)
    b, _ = szamla_draft.letrehoz(db, adat, admin)
    assert b.allapot == ALLAPOT_ELLENORZENDO
    assert b.cel_tipus == "kulsos_tig" and b.cel_certificate_id == t.id and b.szerzodes_id == c.id
    assert b.validacio["ellenorzesek"]["szerzodes"]["tipus"] == "keretszerzodes"
    assert any("eltér" in f for f in b.validacio["figyelmeztetesek"])  # 95 000 vs 100 000
    # Ugyanaz a beküldés még egyszer: ugyanaz a piszkozat, nem új.
    b2, mar = szamla_draft.letrehoz(db, adat, admin)
    assert mar and b2.id == b.id
    # Ugyanaz a számlaszám eltérő összeggel: ütközés.
    with pytest.raises(szamla_draft.DraftUtkozes):
        szamla_draft.letrehoz(db, adat.model_copy(update={"netto": Decimal("1"), "afa_osszeg": Decimal("0"), "brutto": Decimal("1")}), admin)


def test_lejart_keretszerzodes_es_piszkozat_tig_nem_eleg(db, admin, kornyezet):
    c = _keretszerzodes(db, kornyezet)
    c.idoszakok[0].veg = kornyezet["nap"] - timedelta(days=1)
    _tig(db, kornyezet, allapot="Készítés alatt")
    b, _ = szamla_draft.letrehoz(db, _bemenet(kornyezet), admin)
    assert b.allapot == ALLAPOT_HIANYZO_DOKUMENTUMOK
    hiany = {h["dokumentum"]: h["ok"] for h in b.validacio["hianyzo"]}
    assert "nem érvényes" in hiany["keretszerzodes"] and "piszkozat" in hiany["tig"].lower()
    assert "tig_piszkozat_kiegeszitese" in {o["kod"] for o in b.validacio["elokeszitesi_opciok"]}


def test_ujravalidalas_a_hianyzo_dokumentum_utan(db, admin, kornyezet):
    b, _ = szamla_draft.letrehoz(db, _bemenet(kornyezet), admin)
    assert b.allapot == ALLAPOT_HIANYZO_DOKUMENTUMOK
    _keretszerzodes(db, kornyezet)
    t = _tig(db, kornyezet)
    szamla_draft.validal(db, b, user=admin)
    assert b.allapot == ALLAPOT_ELLENORZENDO and b.cel_certificate_id == t.id
    utolso = _auditok(db, b.id)[-1]
    assert utolso.reszletek["allapot_elotte"] == ALLAPOT_HIANYZO_DOKUMENTUMOK
    assert utolso.reszletek["allapot_utana"] == ALLAPOT_ELLENORZENDO


# ── Pénzügyi állapotváltozás csak explicit megerősítéssel ────────────────────


def _kliens(db, admin):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    return TestClient(app), app


def test_api_draft_jovahagyas_csak_megerositessel(db, admin, kornyezet, tarhely):
    _keretszerzodes(db, kornyezet)
    t = _tig(db, kornyezet)
    c, app = _kliens(db, admin)
    eredeti_commit, eredeti_rollback = db.commit, db.rollback
    db.commit = db.flush
    # A végpont hibaágban rollbackel: a tesztben ez egy mentési pontra
    # görgessen vissza, ne a teljes demó-környezetre.
    db.rollback = lambda: None
    try:
        adat = _bemenet(kornyezet).model_dump(mode="json")
        r = c.post("/api/v1/bejovo-szamlak/draft", json=adat)
        assert r.status_code == 201, r.text
        sz = r.json()["szamla"]
        bid = sz["id"]
        assert sz["allapot"] == ALLAPOT_ELLENORZENDO and sz["megerosites_kell"] is True
        assert c.post("/api/v1/bejovo-szamlak/draft", json={**adat, "partner_adoszam": "12"}).status_code == 422

        # A fájl csatolása nem írja felül a strukturált adatot (nincs AI-kiolvasás).
        r = c.post(f"/api/v1/bejovo-szamlak/{bid}/fajl", files={"file": ("szamla.pdf", b"%PDF-1.4 demo", "application/pdf")})
        assert r.status_code == 200, r.text
        sz = r.json()
        assert sz["netto"] == 100000.0 and sz["allapot"] == ALLAPOT_ELLENORZENDO
        kod = sz["ellenorzo_kod"]

        # 1) megerősítés nélkül: 428, semmi nem változik
        r = c.post(f"/api/v1/bejovo-szamlak/{bid}/jovahagyas", json={"cel_tipus": "kulsos_tig"})
        assert r.status_code == 428
        # 2) elavult kóddal: 409
        r = c.post(
            f"/api/v1/bejovo-szamlak/{bid}/jovahagyas",
            json={"cel_tipus": "kulsos_tig", "megerosites": {"megerositve": True, "ellenorzo_kod": "0" * 16}},
        )
        assert r.status_code == 409
        # 3) "megerositve": false: 428
        r = c.post(
            f"/api/v1/bejovo-szamlak/{bid}/jovahagyas",
            json={"cel_tipus": "kulsos_tig", "megerosites": {"megerositve": False, "ellenorzo_kod": kod}},
        )
        assert r.status_code == 428
        b = db.get(BejovoSzamla, bid)
        assert b.allapot == ALLAPOT_ELLENORZENDO and not db.get(PerformanceCertificate, t.id).invoices

        # 4) explicit, friss megerősítéssel: rögzít (a TIG-hez csatol), de
        #    kifizetettnek NEM jelöl.
        r = c.post(
            f"/api/v1/bejovo-szamlak/{bid}/jovahagyas",
            json={"cel_tipus": "kulsos_tig", "megerosites": {"megerositve": True, "ellenorzo_kod": kod}},
        )
        assert r.status_code == 200, r.text
        assert r.json()["allapot"] == ALLAPOT_JOVAHAGYVA
        db.refresh(t)
        assert len(t.invoices) == 1 and t.szamla_kifizetve is False

        naplo = c.get(f"/api/v1/bejovo-szamlak/{bid}/audit").json()
        jovahagyasok = [n for n in naplo if n["muvelet"] == "szamla.jovahagyas"]
        assert sorted(n["eredmeny"] for n in jovahagyasok) == ["elutasitva", "elutasitva", "elutasitva", "ok"]
        ok = next(n for n in jovahagyasok if n["eredmeny"] == "ok")
        assert ok["reszletek"]["explicit_megerosites"] is True and ok["employee_id"] == admin.id
        assert ok["reszletek"]["javasolt_cel"] == {"cel_certificate_id": t.id}
    finally:
        db.commit, db.rollback = eredeti_commit, eredeti_rollback
        app.dependency_overrides.clear()


def test_audit_nem_tarol_erzekeny_kulcsot(db):
    from app.services import automatizalas_audit

    sor = automatizalas_audit.naplo(
        db, muvelet="teszt.demo", eroforras_tipus="demo", eroforras_id=None,
        reszletek={"iban": "HU00 1111", "email_szoveg": "titok", "netto": 5, "belso": {"token": "x", "ok": 1}},
    )
    assert sor.reszletek == {"netto": 5, "belso": {"ok": 1}}
    with pytest.raises(ValueError):
        automatizalas_audit.naplo(db, muvelet="x", eroforras_tipus="demo", eroforras_id=None, szereplo="valaki")


# ── Utókövetés: hiányzó dokumentumok + emlékeztetők ──────────────────────────


def _sor(adat: dict, k: dict) -> dict | None:
    return next((s for s in adat["sorok"] if s["project_id"] == k["p"].id), None)


def test_hianyok_matrix_es_emlekezteto(db, admin, kornyezet):
    adat = utokovetes_hianyok.matrix(db, napok=30)
    sor = _sor(adat, kornyezet)
    assert sor is not None and sor["szamlazo_kulcs"] == f"v{kornyezet['v'].id}"
    assert sor["tagok"] == ["Világosító (demó) Bence"] and sor["lezajlott_napja"] == 10
    d = sor["dokumentumok"]
    assert d["szerzodes"]["allapot"] == "hianyzik" and d["tig"]["allapot"] == "hianyzik"
    assert d["szamla"]["allapot"] == "tig_utan" and sor["hianyzo"] == ["szerzodes", "tig"]
    assert d["tig"]["emlekezteto_db"] == 0 and d["tig"]["utolso_ertesites_at"] is None

    # Emlékeztető rögzítése: darabszám, idő, állapot az értesítéskor + audit.
    utokovetes_hianyok.emlekezteto_rogzitese(
        db, project_id=kornyezet["p"].id, szamlazo_kulcs=sor["szamlazo_kulcs"], dokumentum_tipus="tig",
        csatorna="email", megjegyzes="(demó) első szólás", user=admin,
    )
    rekord = utokovetes_hianyok.emlekezteto_rogzitese(
        db, project_id=kornyezet["p"].id, szamlazo_kulcs=sor["szamlazo_kulcs"], dokumentum_tipus="tig",
        csatorna="telefon", megjegyzes=None, user=admin,
    )
    assert rekord.emlekezteto_db == 2 and rekord.allapot_ertesiteskor == "hianyzik"
    assert db.scalar(
        select(func.count(AutomatizalasAudit.id)).where(
            AutomatizalasAudit.muvelet == "utokovetes.emlekezteto", AutomatizalasAudit.eroforras_id == rekord.id
        )
    ) == 2

    # A TIG kiküldése után: a TIG kész, a számla válik hiányzóvá; a cella
    # jelzi, hogy az utolsó emlékeztető óta változott az állapot.
    _keretszerzodes(db, kornyezet)
    _tig(db, kornyezet)
    sor = _sor(utokovetes_hianyok.matrix(db, napok=30), kornyezet)
    d = sor["dokumentumok"]
    assert d["szerzodes"]["allapot"] == "keretszerzodes" and d["tig"]["allapot"] == "kikuldve"
    assert d["szamla"]["allapot"] == "hianyzik" and sor["hianyzo"] == ["szamla"]
    assert d["tig"]["emlekezteto_db"] == 2 and d["tig"]["valtozott_ertesites_ota"] is True
    assert d["tig"]["utolso_ertesites_csatorna"] == "telefon"
    # Kész dokumentumról nem rögzíthető emlékeztető.
    with pytest.raises(utokovetes_hianyok.HianyHiba):
        utokovetes_hianyok.emlekezteto_rogzitese(
            db, project_id=kornyezet["p"].id, szamlazo_kulcs=sor["szamlazo_kulcs"], dokumentum_tipus="tig",
            csatorna="email", megjegyzes=None, user=admin,
        )


def test_hianyok_beerkezett_draft_szamla_tig_nelkul_es_szures(db, admin, kornyezet):
    b, _ = szamla_draft.letrehoz(db, _bemenet(kornyezet), admin)
    sor = _sor(utokovetes_hianyok.matrix(db, napok=30), kornyezet)
    assert sor["dokumentumok"]["szamla"]["allapot"] == "beerkezett_tig_nelkul"
    assert b.id in sor["dokumentumok"]["szamla"]["erkeztetoben_idk"]
    # A jövőbeli (még le nem zajlott) és a túl régi forgatás nem szerepel.
    kornyezet["p"].forgatas_datuma = MA + timedelta(days=3)
    db.flush()
    assert _sor(utokovetes_hianyok.matrix(db, napok=30), kornyezet) is None
    kornyezet["p"].forgatas_datuma = MA - timedelta(days=60)
    db.flush()
    assert _sor(utokovetes_hianyok.matrix(db, napok=30), kornyezet) is None
    assert _sor(utokovetes_hianyok.matrix(db, napok=90), kornyezet) is not None


def test_api_hianyok_utvonal_es_emlekezteto(db, admin, kornyezet):
    c, app = _kliens(db, admin)
    eredeti = db.commit
    db.commit = db.flush
    try:
        r = c.get("/api/v1/utokovetes/hianyok", params={"napok": 30, "project_id": kornyezet["p"].id})
        assert r.status_code == 200, r.text  # nem nyeli el a /utokovetes/{project_id}
        adat = r.json()
        assert adat["sor_db"] == 1 and adat["hianyzo_osszesito"]["tig"] == 1
        kulcs = adat["sorok"][0]["szamlazo_kulcs"]
        r = c.post(
            "/api/v1/utokovetes/hianyok/emlekezteto",
            json={"project_id": kornyezet["p"].id, "szamlazo_kulcs": kulcs, "dokumentum_tipus": "szerzodes"},
        )
        assert r.status_code == 200 and r.json()["emlekezteto_db"] == 1
        assert c.post(
            "/api/v1/utokovetes/hianyok/emlekezteto",
            json={"project_id": kornyezet["p"].id, "szamlazo_kulcs": "x1", "dokumentum_tipus": "szerzodes"},
        ).status_code == 422
        assert db.scalar(
            select(UtokovetesDokumentum).where(UtokovetesDokumentum.project_id == kornyezet["p"].id)
        ).emlekezteto_db == 1
    finally:
        db.commit = eredeti
        app.dependency_overrides.clear()


def test_uj_modulok_nem_valtoztatnak_penzugyi_allapotot():
    """Forrásszintű őr: a piszkozat- és hiány-szolgáltatás sosem ír kifizetési
    vagy rögzítési állapotot, és nem hívja a jóváhagyást."""
    import inspect

    from app.services import automatizalas_audit

    for modul in (szamla_draft, utokovetes_hianyok, automatizalas_audit):
        forras = inspect.getsource(modul)
        for tiltott in ("szamla_kifizetve =", ".kesz =", "jovahagy(", "ALLAPOT_JOVAHAGYVA\n    bejovo.allapot", "send_email", "google_email"):
            assert tiltott not in forras, f"{modul.__name__}: {tiltott}"


def test_lara_vegrehajto_nem_rogzithet_gepi_piszkozatot(db, admin, kornyezet):
    from types import SimpleNamespace

    from app.admin_agent.executor import VegrehajtasHiba, _run_szamla_jovahagy

    _keretszerzodes(db, kornyezet)
    _tig(db, kornyezet)
    b, _ = szamla_draft.letrehoz(db, _bemenet(kornyezet), admin)
    assert b.allapot == ALLAPOT_ELLENORZENDO
    task = SimpleNamespace(forras_referenciak={"bejovo_szamla_id": b.id})
    proposal = SimpleNamespace(payload={"cel_tipus": "kulsos_tig"})
    with pytest.raises(VegrehajtasHiba):
        _run_szamla_jovahagy(db, proposal, task, admin)
    assert b.allapot == ALLAPOT_ELLENORZENDO
