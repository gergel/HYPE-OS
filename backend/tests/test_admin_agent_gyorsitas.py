"""Lara — gyorsított tanulás: új megfigyelt források, automatikus megerősítés,
szabályjavaslat, jelentés szerinti keresés, napi összesítő, kérdés-értesítés.

Postgres-integráció, DB nélkül self-skip. Minden teszt EGY tranzakcióban fut és
a végén rollback — semmi nem marad az adatbázisban (az API-teszt a saját
sorait maga törli).
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import embedding
from app.admin_agent.megerosites import AUTO, futtat
from app.admin_agent.observer import megfigyeles
from app.models.admin_agent import ActionTrace, LaraKerdes, MemoryChunk, PlaybookRule
from app.models.finance import Expense, Revenue
from app.models.notification import Notification
from app.models.project_code import ProjectCode


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
        embedding.teszt_beagyazo(None)
        sess.rollback()
        sess.close()


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _limitek(db, **kv):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.limitek = {**(s.limitek or {}), **kv}
    db.flush()


def _pelda(db, forras: str) -> MemoryChunk | None:
    return db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras))


def _kod(db, kod: str, megrendelo: str, nev: str = "Gyorsteszt projekt") -> ProjectCode:
    pc = ProjectCode(projektkod=kod, megrendelo_neve=megrendelo, project_nev=nev, datum=date.today())
    db.add(pc)
    db.flush()
    return pc


# ── Új források ──────────────────────────────────────────────────────────────


def test_uj_forrasok_jeloltet_adnak(db):
    """Megrendelői szerződés, projektkód-komment, bevétel, utalás-felvezetés,
    árajánlat és végleges törlés → példa-jelölt a megfelelő tudás-körben; a rövid
    komment, az árajánlat-SABLON és a visszaállított törlés NEM."""
    from app.models.arajanlat import Arajanlat
    from app.models.megrendeloi_papir import MegrendeloiSzerzodes
    from app.models.project_code_comment import ProjectCodeComment
    from app.models.utalas_felvezetes import UtalasAdag, UtalasTetel
    from app.models.visszavonas import ToroltRekord

    pc = _kod(db, "GYT-001", "Forrásteszt Megrendelő Zrt.")
    msz = MegrendeloiSzerzodes(project_code_id=pc.id, ceg_neve="Forrásteszt Megrendelő Zrt.", allapot="Kiküldve",
                               megbizas_targya="imázsfilm", netto_osszeg=900000, plusz_afa=True)
    hosszu = ProjectCodeComment(project_code_id=pc.id, employee_id=2,
                                body="A megrendelő kérésére a számlát csak a TIG aláírása után állítjuk ki, mert így kérték.")
    rovid = ProjectCodeComment(project_code_id=pc.id, employee_id=2, body="ok, köszi")
    bev = Revenue(project_code_id=pc.id, netto=900000, fizetes_hatarideje=date(2026, 9, 10), fizetes_datuma=date(2026, 9, 18))
    adag = UtalasAdag(nev="Gyorsteszt adag", utalas_datum=date(2026, 9, 15))
    db.add_all([msz, hosszu, rovid, bev, adag])
    db.flush()
    tetel = UtalasTetel(adag_id=adag.id, kibocsato_nev="Utalásteszt Bt.", szamlaszam="UT-7", netto=50000,
                        cel_tipus="kiadas", elszamolas="hype", fizetesi_hatarido=date(2026, 9, 12),
                        utalas_datum=date(2026, 9, 15), allapot="rogzitve", rogzitve_at=_most())
    ajanlat = Arajanlat(nev="Gyorsteszt imázsfilm ajánlat", ugyfel="Forrásteszt Megrendelő Zrt.", vegosszeg=950000,
                        adat={"blokkok": [{"szekciok": [{"tetelek": [{"nev": "Operatőr", "egysegar": "120000"}]}]}]})
    sablon = Arajanlat(nev="Gyorsteszt sablon", sablon=True, ugyfel="Valaki", vegosszeg=1)
    regen = _most() - timedelta(hours=3)
    torolt = ToroltRekord(tabla="expenses", rekord_id=987654, employee_id=2, created_at=regen, updated_at=regen,
                          adatok={"megnevezes": "Törlésteszt Kft.", "netto": 1234, "created_at": (regen - timedelta(minutes=5)).isoformat()})
    visszahozott = ToroltRekord(tabla="expenses", rekord_id=987655, employee_id=2, created_at=regen, updated_at=regen,
                                visszaallitva=True, adatok={"megnevezes": "Visszahozott Kft."})
    db.add_all([tetel, ajanlat, sablon, torolt, visszahozott])
    db.flush()

    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()

    m = _pelda(db, f"megfigyeles:megrendeloi_szerzodes:{msz.id}")
    assert m is not None and m.hatokor == "szerzodes" and "Forrásteszt" in m.tartalom and m.ervenyes is False
    k = _pelda(db, f"megfigyeles:projektkod_komment:{hosszu.id}")
    assert k is not None and k.hatokor == "projektkod" and "TIG aláírása után" in k.tartalom and "GYT-001" in k.tartalom
    assert _pelda(db, f"megfigyeles:projektkod_komment:{rovid.id}") is None
    b = _pelda(db, f"megfigyeles:bevetel:{bev.id}")
    assert b is not None and b.hatokor == "kintlevoseg" and "8 nappal a határidő" in b.tartalom
    u = _pelda(db, f"megfigyeles:utalas:{tetel.id}")
    assert u is not None and u.hatokor == "szamla" and "kiadásként" in u.tartalom and "3 nappal a határidő után" in u.tartalom
    a = _pelda(db, f"megfigyeles:arajanlat:{ajanlat.id}")
    assert a is not None and a.hatokor == "arajanlat" and "Operatőr" in a.tartalom and "GYT-001" in a.tartalom
    assert _pelda(db, f"megfigyeles:arajanlat:{sablon.id}") is None
    t = _pelda(db, f"megfigyeles:torles:{torolt.id}")
    assert t is not None and t.hatokor == "szamla" and "TÖRÖLT" in t.tartalom and "Törlésteszt" in t.tartalom
    assert _pelda(db, f"megfigyeles:torles:{visszahozott.id}") is None


# ── Automatikus megerősítés + szabályjavaslat ────────────────────────────────


def _kiadasok(db, partner: str, n: int, tipus: str = "Technika") -> list[Expense]:
    lista = [Expense(megnevezes=partner, netto=10000 + i, brutto=12700, kesz=True, tipus=tipus) for i in range(n)]
    db.add_all(lista)
    db.flush()
    return lista


def test_valosag_igazolta_pelda_automatikusan_jovahagyva(db):
    """3 egybehangzó eset ugyanattól a partnertől → mind automatikusan jóváhagyott
    (nyomvonallal); 2 eset kevés; elvetett példa a csoportban blokkol."""
    _limitek(db, auto_jovahagyas=True, auto_jovahagyas_min=3)
    harom = _kiadasok(db, "Megerősítés Teszt Kft.", 3)
    ketto = _kiadasok(db, "Kevés Eset Bt.", 2)
    blokk = _kiadasok(db, "Blokkolt Csoport Kft.", 3)
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()
    elvetett = _pelda(db, f"megfigyeles:kiadas:{blokk[0].id}")
    elvetett.visszavont = True
    elvetett.minosites = "elvetett"
    db.flush()

    r = futtat(db, trigger="megerosites:teszt")
    db.flush()
    for e in harom:
        p = _pelda(db, f"megfigyeles:kiadas:{e.id}")
        assert p.ervenyes is True and p.minosites == AUTO
        assert db.query(ActionTrace).filter_by(eroforras=f"memory:{p.id}", muvelet="auto_jovahagyas").count() == 1
    for e in ketto:
        assert _pelda(db, f"megfigyeles:kiadas:{e.id}").ervenyes is False
    for e in blokk[1:]:
        assert _pelda(db, f"megfigyeles:kiadas:{e.id}").ervenyes is False
    assert r["auto_jovahagyott"] >= 3 and r["blokkolt_csoport"] >= 1

    # Ember visszavette → többé nem hagyja jóvá magától.
    p = _pelda(db, f"megfigyeles:kiadas:{harom[0].id}")
    p.ervenyes = False
    p.minosites = "kezi_jelolt"
    db.flush()
    futtat(db, trigger="megerosites:teszt")
    assert _pelda(db, f"megfigyeles:kiadas:{harom[0].id}").ervenyes is False

    # Kikapcsolva nem hagy jóvá.
    _limitek(db, auto_jovahagyas=False)
    tovabbi = _kiadasok(db, "Kikapcsolt Teszt Kft.", 3)
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    futtat(db, trigger="megerosites:teszt")
    assert _pelda(db, f"megfigyeles:kiadas:{tovabbi[0].id}").ervenyes is False


def test_szabalyjavaslat_jovahagyott_csoportbol_soha_nem_aktiv(db):
    """5 jóváhagyott, egybehangzó eset → EGY pending szabályjavaslat (magától nem
    élesedik); újrafuttatva nincs duplikátum. Bevételből fizetési-szokás szabály."""
    _limitek(db, auto_jovahagyas=True, auto_jovahagyas_min=3)
    _kiadasok(db, "Szabályjavaslat Teszt Kft.", 5, tipus="Helyszín")
    pc = _kod(db, "GYT-002", "Késve Fizető Zrt.")
    for nap in (5, 9, 13):
        db.add(Revenue(project_code_id=pc.id, netto=100000, fizetes_hatarideje=date(2026, 9, 1),
                       fizetes_datuma=date(2026, 9, 1) + timedelta(days=nap)))
    db.flush()
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    futtat(db, trigger="megerosites:teszt")
    futtat(db, trigger="megerosites:teszt")
    db.flush()

    def _szabalyok(partner_nev):
        return [
            r for r in db.scalars(select(PlaybookRule)).all()
            if (r.feltetelek or {}).get("forras") == "megerosites" and (r.feltetelek or {}).get("partner_nev") == partner_nev
        ]

    sz = _szabalyok("Szabályjavaslat Teszt Kft.")
    assert len(sz) == 1 and sz[0].allapot == "pending" and sz[0].hatokor == "szamla"
    bev = _szabalyok("Késve Fizető Zrt.")
    assert len(bev) == 1 and bev[0].allapot == "pending" and bev[0].hatokor == "kintlevoseg"
    assert "9 nappal a határidő UTÁN" in bev[0].tartalom
    # A bevétel TÉNY: a példák automatikusan jóváhagyottak.
    assert all(
        m.ervenyes for m in db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("megfigyeles:bevetel:%"))).all()
        if "Késve Fizető" in m.tartalom
    )


# ── Jelentés szerinti keresés ────────────────────────────────────────────────


def _hamis_beagyazo(szovegek, _feladat):
    """Determinisztikus „szózsák" vektor: a közös szavak adják a hasonlóságot."""
    ki = []
    for s in szovegek:
        v = [0.0] * embedding.DIM
        for szo in re.findall(r"\w+", s.lower()):
            v[int(hashlib.md5(szo.encode()).hexdigest(), 16) % embedding.DIM] += 1.0
        ki.append(v)
    return ki


def test_jelentes_szerinti_kereses_mas_nev_mellett_is_talal(db, monkeypatch):
    """A jóváhagyott tudás a partner NEVÉNEK egyezése nélkül is előjön, ha a
    jelentése közel van; jelölt nem jön elő; kikapcsolva és hibánál üres."""
    from app.admin_agent.memory import kapcsolodo_tudas

    embedding.teszt_beagyazo(_hamis_beagyazo)
    monkeypatch.setattr(embedding, "MIN_HASONLOSAG", 0.4)
    _limitek(db, szemantikus_kereses=True)
    jo = MemoryChunk(hatokor="szamla", tartalom="drónfelvétel légifotó bérlés számla projektre drónos operatőr",
                     forras="teszt:jelentes", ervenyes=True, minosites="jovahagyott")
    jelolt = MemoryChunk(hatokor="szamla", tartalom="drónfelvétel légifotó bérlés számla jelölt",
                         forras="teszt:jelentes2", ervenyes=False, minosites="jelolt")
    db.add_all([jo, jelolt])
    db.flush()
    r = embedding.feltolt(db, max_db=5000, max_mp=60)
    assert r["beagyazva"] >= 2 and jo.embedding and jo.embedding_modell == embedding.modell()

    t = kapcsolodo_tudas(db, hatokor="szamla", partner="Teljesen Más Nevű Kft.",
                         szoveg="drónfelvétel légifotó bérlés számla")
    idk = [x["id"] for x in t["hasonlo_jelentes"]]
    assert jo.id in idk and jelolt.id not in idk
    assert t["hasonlo_esetek"] == []  # a név szerinti út nem talált volna

    _limitek(db, szemantikus_kereses=False)
    assert kapcsolodo_tudas(db, hatokor="szamla", partner="X", szoveg="drónfelvétel")["hasonlo_jelentes"] == []

    _limitek(db, szemantikus_kereses=True)

    def _hibas(_s, _f):
        raise RuntimeError("modellhiba")

    embedding.teszt_beagyazo(_hibas)
    assert kapcsolodo_tudas(db, hatokor="szamla", partner="X", szoveg="drónfelvétel")["hasonlo_jelentes"] == []


# ── Összesítő + kérdés-értesítés ────────────────────────────────────────────


def test_ertekrangsor_es_napi_osszesito(db, monkeypatch):
    """Több eset ugyanattól a partnertől → előrébb a rangsorban; az összesítő a
    jóváhagyásra jogosultaknak értesítést ír, kikapcsolva nem."""
    from app.admin_agent import osszesito
    from app.models.employee import Employee

    _limitek(db, auto_jovahagyas=False, napi_osszesito=True)
    sok = _kiadasok(db, "Rangsor Sok Eset Kft.", 3)
    egy = _kiadasok(db, "Rangsor Egy Eset Bt.", 1)
    megfigyeles(db, kenyszeritett=True, visszatekintes_nap=1)
    db.flush()
    rangsor = osszesito.ertek_rangsor(db)
    hely = {m.forras: i for i, (_, m, _) in enumerate(rangsor)}
    assert hely[f"megfigyeles:kiadas:{sok[0].id}"] < hely[f"megfigyeles:kiadas:{egy[0].id}"]
    okok = next(o for _, m, o in rangsor if m.forras == f"megfigyeles:kiadas:{sok[0].id}")
    assert any("ugyanattól a partnertől" in o for o in okok)

    emp = db.get(Employee, 2)
    if emp is None:
        pytest.skip("Nincs 2-es munkatárs a fejlesztői adatbázisban.")
    monkeypatch.setattr(osszesito, "lara_felelosok", lambda _db, **_: [emp])
    elotte = db.query(Notification).filter_by(employee_id=emp.id, kind="lara_osszesito").count()
    r = osszesito.napi_osszesito(db)
    assert r["ertesitve"] == 1 and r["varakozo"] >= 4
    assert db.query(Notification).filter_by(employee_id=emp.id, kind="lara_osszesito").count() == elotte + 1

    _limitek(db, napi_osszesito=False)
    assert osszesito.napi_osszesito(db)["ertesitve"] == 0


def test_uj_kerdesrol_ertesites_osszevonva(db, monkeypatch):
    """Egy új kérdés → konkrét értesítés; több → EGY összefoglaló címzettenként;
    kikapcsolva semmi."""
    from app.admin_agent import osszesito
    from app.models.employee import Employee

    emp = db.get(Employee, 2)
    if emp is None:
        pytest.skip("Nincs 2-es munkatárs a fejlesztői adatbázisban.")
    monkeypatch.setattr(osszesito, "lara_felelosok", lambda _db, **_: [emp])
    _limitek(db, kerdes_ertesites=True)
    k1 = LaraKerdes(tipus="papir", allapot="nyitott", kulcs="gyt|1", partner_nev="Kérdés Egy Kft.", kerdes="Miért maradt ki a TIG?")
    k2 = LaraKerdes(tipus="papir", allapot="nyitott", kulcs="gyt|2", partner_nev="Kérdés Kettő Kft.", kerdes="Miért +ÁFA?")
    db.add_all([k1, k2])
    db.flush()

    elotte = db.query(Notification).filter_by(employee_id=emp.id, kind="lara_kerdes").count()
    assert osszesito.kerdes_ertesites(db, [k1]) == 1
    uj = db.query(Notification).filter_by(employee_id=emp.id, kind="lara_kerdes").order_by(Notification.id.desc()).first()
    assert "Kérdés Egy Kft." in uj.message and uj.link == "/admin-agent/kerdesek"
    assert osszesito.kerdes_ertesites(db, [k1, k2]) == 1
    uj = db.query(Notification).filter_by(employee_id=emp.id, kind="lara_kerdes").order_by(Notification.id.desc()).first()
    assert "2 új kérdése" in uj.message
    assert db.query(Notification).filter_by(employee_id=emp.id, kind="lara_kerdes").count() == elotte + 2

    _limitek(db, kerdes_ertesites=False)
    assert osszesito.kerdes_ertesites(db, [k1]) == 0


# ── API ──────────────────────────────────────────────────────────────────────


def test_gyorsitas_api(db):
    """GET /learning-boost szerkezete; /memory?rendezes=ertek érték-mezőkkel;
    automatikusan jóváhagyott példa visszavétele „kezi_jelolt" lesz."""
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    m = MemoryChunk(hatokor="szamla", tartalom="API gyorsteszt", forras="teszt:gyors-api", ervenyes=True, minosites=AUTO)
    db.add(m)
    db.commit()
    mid = m.id
    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
        r = c.get("/api/v1/admin-agent/learning-boost", headers=h)
        assert r.status_code == 200
        d = r.json()
        assert set(d) >= {"beallitasok", "megerosites", "beagyazas", "varakozo", "legertekesebb"}
        assert set(d["beallitasok"]) == {"auto_jovahagyas", "auto_jovahagyas_min", "szemantikus_kereses",
                                         "napi_osszesito", "kerdes_ertesites"}
        r = c.get("/api/v1/admin-agent/memory?rendezes=ertek&limit=50", headers=h)
        assert r.status_code == 200
        r = c.patch(f"/api/v1/admin-agent/memory/{mid}", headers=h, json={"ervenyes": False})
        assert r.status_code == 200 and r.json()["minosites"] == "kezi_jelolt"
    finally:
        db.query(MemoryChunk).filter(MemoryChunk.id == mid).delete(synchronize_session=False)
        db.commit()


def test_szoveg_valtozasa_ervenyteleniti_a_vektort(db):
    """Ha a tudás-darab szövege megváltozik, a régi vektora törlődik (a következő
    beágyazás újraszámolja) — elavult vektor nem adhat hamis találatot."""
    embedding.teszt_beagyazo(_hamis_beagyazo)
    m = MemoryChunk(hatokor="szamla", tartalom="régi szöveg", forras="teszt:vektor", ervenyes=True, minosites="jovahagyott")
    db.add(m)
    db.flush()
    embedding.feltolt(db, max_db=5000)
    assert m.embedding
    m.tartalom = "új szöveg"
    assert m.embedding is None and m.embedding_modell is None
