"""Lara — TIG/szerződés/e-mail tervezet tesztjei.

VALÓDI MODELLHÍVÁS NINCS: a hamis adapter (`llm.teszt_adapter`) adja a választ.
A teendő-listát és a tudást monkeypatch-csel adjuk, így a tervező logikája
(forrás-sorrend, összeg-őr, címzett-őr) adatbázis nélkül ellenőrizhető. A
piszkozat-mentés végrehajtóját a dev-adatbázis egy valódi függő tételén
futtatjuk (rollback), ha van ilyen.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import llm, tervezo


@pytest.fixture(autouse=True)
def _adapter_vissza():
    yield
    llm.teszt_adapter(None)


def _teendo(**kw):
    alap = {
        "project_id": 11,
        "project_nev": "Forgatás",
        "projektkod": "HYPE26-0001",
        "teljesites_alap": None,
        "szamlazo_kulcs": "emp:5",
        "nev": "Forgató Feri",
        "cimke": None,
        "email": "feri@example.com",
        "partner": {"ceg_neve": "Feri Bt."},
        "draft": {},
        "szerzodes": {},
        "tetel_osszeg": None,
        "tetelek": [],
    }
    alap.update(kw)
    return alap


def _nincs_tudas(db, *, hatokor, partner):
    return {"szabalyok": [], "hasonlo_esetek": []}


def _feladat(**kw):
    alap = dict(tipus="tig", project_code_id=1, cim="TIG", osszefoglalo=None, partner_nev=None)
    alap.update(kw)
    return SimpleNamespace(**alap)


# ── Tiszta függvények ────────────────────────────────────────────────────────


def test_elotoltes_forras_sorrend():
    t = _teendo(
        draft={"megbizas_targya": "Piszkozat tárgy"},
        szerzodes={"megbizas_targya": "Szerződés tárgy", "netto_osszeg": 50000},
        partner={"ceg_neve": "Feri Bt.", "megbizas_targya": "Törzs tárgy"},
        teljesites_alap="2026.09.01–2026.09.03",
        tetel_osszeg=70000,
    )
    mezok, forras, igazolt = tervezo._elotoltes("tig", t)
    assert mezok["megbizas_targya"] == "Piszkozat tárgy" and forras["megbizas_targya"] == "mentett piszkozat"
    assert mezok["netto_osszeg"] == 50000 and forras["netto_osszeg"] == "eseti szerződés"
    assert forras["ceg_neve"] == "partnertörzs"
    assert forras["teljesites_szoveg"] == "a projekt dátumai"
    assert igazolt == {50000.0, 70000.0}


def test_peldak_osszegei_szokozos_ezres_tagolassal():
    peldak = [{"tartalom": "HYPE26-1 · X — TIG: Feri, állapot: Kiküldve, nettó 135 000 Ft."}, {"tartalom": "nincs összeg"}]
    assert tervezo._peldak_osszegei(peldak) == {135000.0}


def test_validate_tervezet_hianyzo_kotelezo_mezok():
    v = tervezo.validate_tervezet("tig")
    hibak = v({"tetelek": [{"nev": "Feri", "project_nev": "P", "project_id": 1, "szamlazo_kulcs": "emp:5",
                            "mezok": {"megbizas_targya": "Vágás"}}]})
    assert len(hibak) == 1 and "nettó összeg" in hibak[0] and "teljesítés" in hibak[0]
    assert v({"tetelek": []}) == ["Nincs egyetlen tétel sem a tervezetben."]


# ── Tervezet a modellel (hamis adapter) ─────────────────────────────────────


def _modell(tetel: dict):
    return lambda r, f, s: {"tetelek": [{"index": 0, "indoklas": "korábbi eset", **tetel}]}


def test_modell_igazolt_osszeget_elfogad(monkeypatch):
    monkeypatch.setattr(tervezo, "teendok", lambda db, tipus, pc, user: [_teendo()])
    monkeypatch.setattr(
        tervezo, "kapcsolodo_tudas",
        lambda db, *, hatokor, partner: {"szabalyok": [], "hasonlo_esetek": [
            {"tartalom": "HYPE26-0002 · Előző — TIG: Forgató Feri, állapot: Kiküldve, nettó 70 000 Ft."}]},
    )
    llm.teszt_adapter(_modell({"megbizas_targya": "Forgatási asszisztencia", "netto_osszeg": 70000,
                               "teljesites_szoveg": "2026. szeptember"}))
    k = tervezo.tig_szerzodes_tervezet(None, _feladat(), None)
    t = k["payload"]["tetelek"][0]
    assert t["mezok"]["netto_osszeg"] == 70000
    assert t["forrasok"]["netto_osszeg"] == "Lara (igazolt korábbi összeg)"
    assert t["forrasok"]["megbizas_targya"] == "Lara (korábbi esetek alapján)"
    assert k["modell"]["allapot"] == "kesz"
    assert k["eszkoz"] == "tig.piszkozat_mentes"


def test_modell_kitalalt_osszeget_elutasit(monkeypatch):
    monkeypatch.setattr(tervezo, "teendok", lambda db, tipus, pc, user: [_teendo()])
    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    llm.teszt_adapter(_modell({"megbizas_targya": "Vágás", "netto_osszeg": 99999, "teljesites_szoveg": ""}))
    k = tervezo.tig_szerzodes_tervezet(None, _feladat(), None)
    t = k["payload"]["tetelek"][0]
    assert "netto_osszeg" not in t["mezok"]
    assert any("nincs igazolt forrásban" in f for f in k["modell"]["figyelmeztetesek"])
    # A hiány a validátoron fennakad → emberhez kerül.
    assert tervezo.validate_tervezet("tig")(k["payload"])


def test_modell_nem_irja_felul_az_ismert_mezot(monkeypatch):
    monkeypatch.setattr(
        tervezo, "teendok",
        lambda db, tipus, pc, user: [_teendo(draft={"megbizas_targya": "Emberi tárgy"}, tetel_osszeg=40000)],
    )
    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    llm.teszt_adapter(_modell({"megbizas_targya": "Modell tárgy", "netto_osszeg": 1, "teljesites_szoveg": "szept."}))
    t = tervezo.tig_szerzodes_tervezet(None, _feladat(), None)["payload"]["tetelek"][0]
    assert t["mezok"]["megbizas_targya"] == "Emberi tárgy"
    assert t["mezok"]["netto_osszeg"] == 40000
    assert t["mezok"]["teljesites_szoveg"] == "szept."


def test_kulcs_nelkul_determinista_elotoltes(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(tervezo, "teendok", lambda db, tipus, pc, user: [_teendo(tetel_osszeg=30000)])
    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    k = tervezo.tig_szerzodes_tervezet(None, _feladat(), None)
    assert k["modell"]["allapot"] == "beallitas_szukseges"
    assert k["payload"]["tetelek"][0]["mezok"]["netto_osszeg"] == 30000


def test_projektkod_nelkul_nincs_tervezet():
    with pytest.raises(tervezo.TervezetHiba):
        tervezo.tig_szerzodes_tervezet(None, _feladat(project_code_id=None), None)


def test_email_csak_igazolt_cimzett(monkeypatch):
    monkeypatch.setattr(tervezo, "ismert_cimek", lambda db, task, user: [
        {"email": "ugyfel@example.com", "nev": "Ügyfél", "forras": "megrendelő kontakt"}])
    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    llm.teszt_adapter(lambda r, f, s: {"to": ["Ugyfel@example.com", "tamado@evil.test"], "subject": "Tárgy",
                                       "html_body": "<p>Szia</p>", "indoklas": "x"})
    k = tervezo.email_tervezet(None, _feladat(tipus="email", project_code_id=None), None)
    assert k["payload"]["to"] == ["ugyfel@example.com"]
    assert any("tamado@evil.test" in f for f in k["modell"]["figyelmeztetesek"])
    assert k["extra_hianyok"] == []


def test_email_ismeretlen_cimzett_eseten_hiany(monkeypatch):
    monkeypatch.setattr(tervezo, "ismert_cimek", lambda db, task, user: [])
    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    llm.teszt_adapter(lambda r, f, s: {"to": ["x@y.test"], "subject": "T", "html_body": "<p>x</p>", "indoklas": "x"})
    k = tervezo.email_tervezet(None, _feladat(tipus="email", project_code_id=None), None)
    assert k["payload"]["to"] == [] and k["extra_hianyok"]


def test_email_modell_nelkul_hiba(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(tervezo, "ismert_cimek", lambda db, task, user: [])
    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    with pytest.raises(tervezo.TervezetHiba):
        tervezo.email_tervezet(None, _feladat(tipus="email", project_code_id=None), None)


# ── Piszkozat-mentés a meglévő úton (dev-adat, rollback) ─────────────────────


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


def test_piszkozat_mentes_meglevo_uton(db, monkeypatch):
    from app.models.employee import Employee
    from app.models.project_code import ProjectCode

    monkeypatch.setattr(tervezo, "kapcsolodo_tudas", _nincs_tudas)
    llm.teszt_adapter(lambda r, f, s: {"tetelek": []})
    user = db.scalars(select(Employee).where(Employee.role == "admin").order_by(Employee.id)).first()
    if user is None:
        pytest.skip("Nincs admin felhasználó a dev-adatbázisban.")
    for pc_id in db.scalars(select(ProjectCode.id).order_by(ProjectCode.id).limit(40)).all():
        for tipus in ("szerzodes", "tig"):
            if tervezo.teendok(db, tipus, pc_id, user):
                break
        else:
            continue
        break
    else:
        pytest.skip("Nincs függő TIG/szerződés a dev-adatbázisban.")

    k = tervezo.tig_szerzodes_tervezet(db, _feladat(tipus=tipus, project_code_id=pc_id), user)
    t = k["payload"]["tetelek"][0]
    t["mezok"].update({"megbizas_targya": "Teszt tárgy", "netto_osszeg": 12345, "teljesites_szoveg": "teszt"})
    k["payload"]["tetelek"] = [t]
    assert tervezo.validate_tervezet(tipus)(k["payload"]) == []

    eredmeny = tervezo.piszkozat_mentes_futtato(tipus)(db, SimpleNamespace(payload=k["payload"]), None, user)
    p = eredmeny["piszkozatok"][0]
    assert p["project_id"] == t["project_id"]
    assert p["allapot"] == "Készítés alatt"
