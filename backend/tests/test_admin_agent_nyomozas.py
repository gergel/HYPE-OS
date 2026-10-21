"""Lara utánanézése az AI asszisztens csak-olvasó eszközeivel és tudásával.

Postgres-integráció, DB nélkül self-skip. EGY tranzakció, a végén rollback.
Valódi modellhívás nincs: a modell-beszélgetés hamis (`teszt_beszelgetes`)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import nyomozas
from app.admin_agent.settings_service import get_settings
from app.models.admin_agent import LaraKerdes
from app.models.employee import Employee


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
        nyomozas.teszt_beszelgetes(None)
        sess.rollback()
        sess.close()


@pytest.fixture()
def admin(db):
    e = db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin munkatárs (#2) a teszthez.")
    return e


class _Hamis:
    """Előre megírt modell-körök: minden kör vagy eszközhívás-lista, vagy végső szöveg."""

    def __init__(self, korok, naplo):
        self.korok = list(korok)
        self.naplo = naplo

    def lepes(self):
        kor = self.korok.pop(0)
        if isinstance(kor, str):
            return [], kor
        if isinstance(kor, Exception):
            raise kor
        return kor, None

    def eredmenyek(self, parok):
        self.naplo.extend(parok)


def _hamis(korok, naplo=None, rendszerek=None):
    naplo = naplo if naplo is not None else []

    def gyar(rendszer, kerdes, eszkozok):
        if rendszerek is not None:
            rendszerek.append((rendszer, kerdes, [e["name"] for e in eszkozok]))
        return _Hamis(korok, naplo)

    nyomozas.teszt_beszelgetes(gyar)
    return naplo


def _kerdes(db, **kv) -> LaraKerdes:
    k = LaraKerdes(tipus=kv.get("tipus", "rendszer_elteres"), allapot="nyitott", kulcs=kv.get("kulcs", "nyom|1"),
                   partner_nev=kv.get("partner", "Nyomozás Teszt Kft."), kerdes="Miért nincs papír?",
                   kontextus={"cimke": "A megrendelő fizetett, de nincs papír", "esetek": [{"rekord": "projektkod:1"}]})
    db.add(k)
    db.flush()
    return k


def _veg(**kv) -> str:
    return json.dumps({"valasz": "A projektkódnál a komment szerint keretszerződés fedi.", "javaslat": "mindig",
                       "biztossag": 0.85, "bizonyitekok": [{"leiras": "Komment a projektkódon", "link": "/projektek/1"},
                                                           {"leiras": "Külső link", "link": "https://rossz.example"}],
                       **kv}, ensure_ascii=False)


def test_csak_olvaso_eszkozok_es_az_asszisztens_tudasa(db, admin):
    """Lara pontosan az asszisztens OLVASÓ eszközeit kapja; írót nem, és ha
    mégis kérne, az eszköz-réteg elutasítja. A rendszerüzenetben ott az
    asszisztens tudása (receptek + entitás-séma)."""
    nevek = {e["name"] for e in nyomozas.eszkozok()}
    assert nevek == set(nyomozas.OLVASO_ESZKOZOK)
    assert not nevek & {"api_muvelet", "szamla_feltoltes", "dokumentum_csatolas"}

    rendszerek: list = []
    naplo = _hamis([[("api_muvelet", {"method": "DELETE", "path": "/api/v1/expenses/1"})], _veg()], rendszerek=rendszerek)
    k = _kerdes(db)
    nyomozas.nyomoz(db, k, admin)
    assert naplo[0][0] == "api_muvelet" and "csak olvashat" in naplo[0][1]["error"]
    rendszer, kerdes, eszkozok = rendszerek[0]
    assert "AZ AI ASSZISZTENS TUDÁSA" in rendszer and "globalis_kereses" in rendszer
    assert "projectCode" in rendszer or "project" in rendszer
    assert "Miért nincs papír?" in kerdes and "api_muvelet" not in eszkozok


def test_utananezes_eredmenye_a_kerdesben(db, admin):
    """Az eszköz a futtató nevében, a közös munkamenetben fut; a végső JSON a
    kérdés kontextusába kerül; külső link nem mehet át."""
    from app.models.project_code import ProjectCode

    db.add(ProjectCode(projektkod="NYOM-TESZT-1", megrendelo_neve="Nyomozás Teszt Kft."))
    db.flush()
    naplo = _hamis([
        [("query_entity", {"entity_type": "projectCode", "filters": json.dumps({"projektkod": "NYOM-TESZT-1"})})],
        _veg(),
    ])
    k = _kerdes(db)
    r = nyomozas.nyomoz(db, k, admin)
    talalat = naplo[0][1]
    assert "NYOM-TESZT-1" in json.dumps(talalat, ensure_ascii=False, default=str)
    n = k.kontextus[nyomozas.KULCS]
    assert r == n and n["allapot"] == "kesz" and n["javaslat"] == "mindig" and n["biztossag"] == 0.85
    assert n["futtato_id"] == admin.id and n["lepesek"][0]["eszkoz"] == "query_entity" and n["lepesek"][0]["ok"]
    assert [b["link"] for b in n["bizonyitekok"]] == ["/projektek/1", None]


def test_hiba_es_ertelmezhetetlen_valasz_fail_closed(db, admin):
    _hamis([RuntimeError("429")])
    k = _kerdes(db)
    n = nyomozas.nyomoz(db, k, admin)
    assert n["allapot"] == "hiba" and n["javaslat"] == "nem_tudom"

    _hamis(["Ez nem JSON, csak szöveg."])
    k2 = _kerdes(db, kulcs="nyom|2")
    n2 = nyomozas.nyomoz(db, k2, admin)
    assert n2["javaslat"] == "nem_tudom" and n2["valasz"].startswith("Ez nem JSON")


def test_hatterfutas_a_felelos_neveben_korlattal(db, admin):
    """Csak nyitott, még utána nem nézett kérdés; legfeljebb N; a felelős
    jogosultságával. Kikapcsolva / leállítva nem fut."""
    s = get_settings(db)
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id, "nyomozas": True}
    db.flush()
    for kerd in db.scalars(select(LaraKerdes).where(LaraKerdes.allapot == "nyitott")).all():
        kerd.allapot = "elvetve"
    k1, k2, k3 = (_kerdes(db, kulcs=f"nyom|h{i}") for i in range(3))
    kesz = _kerdes(db, kulcs="nyom|kesz")
    kesz.kontextus = {**kesz.kontextus, nyomozas.KULCS: {"javaslat": "nem_tudom", "futtato_id": admin.id}}
    db.flush()
    _hamis([_veg(), _veg()])
    r = nyomozas.futtat(db, max_db=2)
    assert r["nyomozott"] == 2 and r["valaszt_talalt"] == 2
    assert nyomozas.KULCS in k3.kontextus and nyomozas.KULCS in k2.kontextus and nyomozas.KULCS not in k1.kontextus
    assert k3.kontextus[nyomozas.KULCS]["futtato_id"] == admin.id

    s.limitek = {**s.limitek, "nyomozas": False}
    db.flush()
    assert nyomozas.futtat(db)["allapot"] == "kikapcsolva"


def test_lathatosag_es_elfogadas_statisztika(db, admin):
    """Az eredményt csak a futtató látja; az elfogadás a statisztikába kerül."""
    from app.api.routes.admin_agent import _kerdes_sor

    _hamis([_veg()])
    k = _kerdes(db, kulcs="nyom|lat")
    nyomozas.nyomoz(db, k, admin)
    masik = db.scalars(select(Employee).where(Employee.id != admin.id).limit(1)).first()
    assert nyomozas.KULCS in _kerdes_sor(k, admin)["kontextus"]
    if masik is not None:
        assert nyomozas.KULCS not in _kerdes_sor(k, masik)["kontextus"]
    assert nyomozas.KULCS not in _kerdes_sor(k)["kontextus"]

    elotte = nyomozas.statisztika(db)
    nyomozas.elfogadas_jelolese(k, True)
    db.flush()
    utana = nyomozas.statisztika(db)
    assert utana["elfogadva"] == elotte["elfogadva"] + 1


def test_magabiztos_valasznal_nem_kerdez_csak_ellenorizteti(db, admin, monkeypatch):
    """Ha Lara utánanézve magabiztos választ talál, nem kérdez: „magától
    megválaszolta" állapotba teszi, értesítés nélkül; ahol nem talált, ott
    kérdez (és akkor megy értesítés). Tudás csak elfogadás után lesz."""
    from app.admin_agent import osszesito
    from app.models.admin_agent import MemoryChunk

    ertesitett: list = []
    monkeypatch.setattr(osszesito, "kerdes_ertesites", lambda _db, ks: ertesitett.extend(ks) or len(ks))
    s = get_settings(db)
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id, "nyomozas": True, "onallo_valasz": True}
    for kerd in db.scalars(select(LaraKerdes).where(LaraKerdes.allapot == "nyitott")).all():
        kerd.allapot = "elvetve"
    biztos = _kerdes(db, kulcs="nyom|biztos")
    bizonytalan = _kerdes(db, kulcs="nyom|bizonytalan")
    for k in (biztos, bizonytalan):
        k.kontextus = {**k.kontextus, nyomozas.ERTESITES_FUGGO: True}
    db.flush()
    valaszok = {bizonytalan.id: _veg(biztossag=0.4, javaslat="magyarazat"), biztos.id: _veg(biztossag=0.9)}
    sorrend = [bizonytalan.id, biztos.id]  # a futás a legfrissebbel kezd

    def gyar(rendszer, kerdes, eszkozok):
        return _Hamis([valaszok[sorrend.pop()]], [])

    sorrend.reverse()
    nyomozas.teszt_beszelgetes(gyar)
    r = nyomozas.futtat(db)
    assert r["onallo"] == 1 and r["nyomozott"] == 2
    assert biztos.allapot == nyomozas.ONALLO_ALLAPOT and biztos.valasz_tipus == "mindig" and biztos.valasz_szoveg
    assert bizonytalan.allapot == "nyitott"
    assert [k.id for k in ertesitett] == [bizonytalan.id]
    assert not db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"kerdes:{biztos.id}"))

    # „Nem így" → újra nyitott; utána a felelős válasza a szokásos úton megy.
    from app.api.routes.admin_agent import kerdes_visszanyitas

    monkeypatch.setattr(db, "commit", db.flush)
    kerdes_visszanyitas(biztos.id, db, admin)
    assert biztos.allapot == "nyitott" and biztos.valasz_tipus is None
    assert biztos.kontextus[nyomozas.KULCS]["elutasitva"] is True


def test_uj_kerdes_ertesitese_var_az_utananezesre(db, admin, monkeypatch):
    from app.admin_agent import osszesito
    from app.admin_agent.onellenorzes import onellenorzes
    from app.models.project_code import ProjectCode
    from datetime import date

    hivas: list = []
    monkeypatch.setattr(osszesito, "kerdes_ertesites", lambda _db, ks: hivas.extend(ks) or len(ks))
    s = get_settings(db)
    s.limitek = {**(s.limitek or {}), "felelos_employee_id": admin.id, "nyomozas": True}
    for kerd in db.scalars(select(LaraKerdes).where(LaraKerdes.allapot == "nyitott")).all():
        kerd.allapot = "elvetve"
    db.add(ProjectCode(projektkod="NYOM-ERT-1", megrendelo_neve="Értesítés Teszt Kft.", datum=date.today(),
                       szamla_kihagyva=True))
    db.flush()
    nyomozas.teszt_beszelgetes(lambda *_: _Hamis([_veg()], []))
    r = onellenorzes(db, trigger="onellenorzes:teszt")
    assert r["uj_kerdes"] >= 1 and r["ertesitett"] == 0 and not hivas
    uj = db.scalars(select(LaraKerdes).where(LaraKerdes.allapot == "nyitott")).all()
    assert uj and all((k.kontextus or {}).get(nyomozas.ERTESITES_FUGGO) for k in uj)
