"""Lara: levelezés-olvasás (szamla@ postafiók), teljes vészleállítás, utalás nélkül.

Postgres-integráció (DB nélkül self-skip), egy tranzakcióban, a végén rollback.
VALÓDI GMAIL- ÉS MODELLHÍVÁS NINCS: a Gmail-szolgáltatást egy hamis objektum
helyettesíti.

Fedi: a szálból (bejövő levél + a mi válaszunk + csatolmány) tudás-JELÖLT lesz
az idézett részek nélkül; változatlan szálat nem olvas újra, új levélnél
frissít (a jóváhagyott újra jelölt lesz); a gépi (no-reply) szálból nincs
jelölt; jóváhagyás után az e-mail-tudásban partner szerint előkerül; a
vészleállítás minden szálon megállít (API 423, ütemezett feladat, futás
közben) és a tudás megmarad; utalás-feladat nem hozható létre.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
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


def _b(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")


def _uzenet(uid, ts, felado, cimzett, targy, torzs, *, kimeno=False, csatolmany=None):
    reszek = [{"mimeType": "text/plain", "body": {"data": _b(torzs)}}]
    if csatolmany:
        nev, mime, tartalom = csatolmany
        reszek.append({"filename": nev, "mimeType": mime, "body": {"data": _b(tartalom), "size": len(tartalom)}})
    return {
        "id": uid,
        "internalDate": str(int(ts.timestamp() * 1000)),
        "labelIds": ["SENT"] if kimeno else ["INBOX"],
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": felado},
                {"name": "To", "value": cimzett},
                {"name": "Subject", "value": targy},
            ],
            "parts": reszek,
        },
    }


class _Hivas:
    def __init__(self, ertek):
        self.ertek = ertek

    def execute(self):
        return self.ertek


class HamisGmail:
    """A Gmail API azon része, amit a levelezés-olvasó használ."""

    def __init__(self, szalak: dict[str, dict]):
        self.szalak = szalak
        self.lekert: list[str] = []

    def users(self):
        return self

    def threads(self):
        return self

    def messages(self):
        return self

    def attachments(self):
        return self

    def list(self, userId, q, maxResults, pageToken=None):  # noqa: N803 - Gmail API névhasználat
        assert "szamla@hypestab.hu" in q and "after:" in q
        return _Hivas({"threads": [{"id": k, "historyId": v["historyId"]} for k, v in self.szalak.items()]})

    def get(self, userId, id, format=None, messageId=None):  # noqa: A002, N803
        self.lekert.append(id)
        return _Hivas(self.szalak[id])


def _bekapcsol(db, levelezes=True):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.engedett_forrasok = {**(s.engedett_forrasok or {}), "levelezes": levelezes}
    s.kill_switch = False
    db.flush()


T1 = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)


def _partner_szal(hist="100", harmadik=False):
    uzenetek = [
        _uzenet(
            "lv-m1", T1, "Levélteszt Stúdió Kft. <iroda@levelteszt.hu>", "szamla@hypestab.hu", "Szeptemberi számla",
            "Szia! Csatolom a szeptemberi bérleti számlát, a DEMO26-X01 forgatásra.\n\nÜdv, Kata",
            csatolmany=("szamla.xml", "application/xml", "<Szamla><Osszeg>150000</Osszeg><Targy>Stúdióbérlés</Targy></Szamla>"),
        ),
        _uzenet(
            "lv-m2", T2, "HYPE Számla <szamla@hypestab.hu>", "iroda@levelteszt.hu", "Re: Szeptemberi számla",
            "Köszönjük, rögzítettük a forgatás költségei közé.\n\nOn 2026. 09. 10., Kata wrote:\n> Csatolom a számlát",
            kimeno=True,
        ),
    ]
    if harmadik:
        uzenetek.append(
            _uzenet("lv-m3", T3, "Levélteszt Stúdió Kft. <iroda@levelteszt.hu>", "szamla@hypestab.hu",
                    "Re: Szeptemberi számla", "Rendben, köszönöm!")
        )
    return {"id": "lvteszt-szal-1", "historyId": hist, "messages": uzenetek}


def _chunk(db, szal_id="lvteszt-szal-1"):
    from app.models.admin_agent import MemoryChunk

    return db.scalar(select(MemoryChunk).where(MemoryChunk.forras == f"levelezes:{szal_id}"))


def test_szalbol_tudas_jelolt_idezet_nelkul_es_csatolmannyal(db):
    from app.admin_agent.levelezes import levelezes_tanulas

    _bekapcsol(db)
    gmail = HamisGmail({"lvteszt-szal-1": _partner_szal()})
    e = levelezes_tanulas(db, svc=gmail)
    assert e["allapot"] == "kesz" and e["uj"] == 1
    m = _chunk(db)
    assert m.hatokor == "email" and m.ervenyes is False and m.minosites == "jelolt"
    t = m.tartalom
    assert "Levélteszt Stúdió Kft." in t and "Szeptemberi számla" in t
    assert "2 levél (1 bejövő, 1 válaszunk)" in t
    assert "Csatolom a szeptemberi bérleti számlát" in t
    assert "rögzítettük a forgatás költségei közé" in t
    assert "Kata wrote" not in t and "> Csatolom" not in t  # az idézett rész levágva
    assert "szamla.xml" in t and "150000" in t and "Stúdióbérlés" in t  # csatolmány-kivonat


def test_valtozatlan_szal_nem_olvas_ujra_uj_levelnel_frissit(db):
    from app.admin_agent.levelezes import levelezes_tanulas

    _bekapcsol(db)
    gmail = HamisGmail({"lvteszt-szal-1": _partner_szal()})
    levelezes_tanulas(db, svc=gmail)
    gmail.lekert.clear()
    e = levelezes_tanulas(db, svc=gmail)
    assert e["feldolgozando"] == 0 and "lvteszt-szal-1" not in gmail.lekert

    m = _chunk(db)
    m.ervenyes = True  # jóváhagyva
    m.minosites = "jovahagyott"
    db.flush()
    gmail.szalak["lvteszt-szal-1"] = _partner_szal(hist="200", harmadik=True)
    e = levelezes_tanulas(db, svc=gmail)
    assert e["frissitett"] == 1
    db.refresh(m)
    assert "Rendben, köszönöm!" in m.tartalom and "3 levél" in m.tartalom
    assert m.ervenyes is False and m.minosites == "jelolt"  # új levél → újra ember nézi át


def test_gepi_szalbol_nincs_jelolt_es_jovahagyott_tudas_elokerul(db):
    from app.admin_agent.levelezes import levelezes_tanulas
    from app.admin_agent.memory import kapcsolodo_tudas

    _bekapcsol(db)
    gepi = {
        "id": "lvteszt-gepi",
        "historyId": "5",
        "messages": [_uzenet("lv-g1", T1, "Szolgáltató <no-reply@szolgaltato.hu>", "szamla@hypestab.hu",
                             "Havi értesítő", "Automatikus értesítés.")],
    }
    gmail = HamisGmail({"lvteszt-szal-1": _partner_szal(), "lvteszt-gepi": gepi})
    e = levelezes_tanulas(db, svc=gmail)
    assert e["automatikus"] == 1 and _chunk(db, "lvteszt-gepi") is None

    assert kapcsolodo_tudas(db, hatokor="email", partner="Levélteszt Stúdió Kft.")["hasonlo_esetek"] == []
    m = _chunk(db)
    m.ervenyes = True
    db.flush()
    talalat = kapcsolodo_tudas(db, hatokor="email", partner="Levélteszt Stúdió Kft.")["hasonlo_esetek"]
    assert talalat and "rögzítettük a forgatás költségei közé" in talalat[0]["tartalom"]


def test_kikapcsolt_forras_es_vesz_leallitas_futas_kozben(db, monkeypatch):
    from app.admin_agent import levelezes
    from app.admin_agent.settings_service import get_settings

    _bekapcsol(db, levelezes=False)
    assert levelezes.levelezes_tanulas(db, svc=HamisGmail({}))["allapot"] == "kikapcsolva"

    _bekapcsol(db)
    get_settings(db).kill_switch = True
    db.flush()
    assert levelezes.levelezes_tanulas(db, svc=HamisGmail({}))["allapot"] == "leallitva"

    # Futás KÖZBEN bekapcsolt vészleállítás: a következő ellenőrzési ponton megáll.
    get_settings(db).kill_switch = False
    db.flush()
    szalak = {}
    for i in range(25):
        sz = _partner_szal(hist=str(i))
        sz["id"] = f"lvteszt-sok-{i}"
        for u in sz["messages"]:
            u["id"] = f"{u['id']}-{i}"
        szalak[sz["id"]] = sz
    monkeypatch.setattr(levelezes, "leallitva", lambda db=None: db is None)  # a friss olvasás már „leállítva"
    e = levelezes.levelezes_tanulas(db, svc=HamisGmail(szalak))
    assert e["allapot"] == "leallitva" and e["uj"] == 10


def test_vesz_leallitas_api_es_utemezett_feladat(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.main import app
    from app.models.admin_agent import AdminAgentSetting
    from app.workers import admin_agent_tasks

    # Az API saját munkamenetben olvas: a kapcsolót commitálva kell beállítani,
    # a végén pedig visszaállítani.
    from sqlalchemy import delete, func

    from app.models.admin_agent import ActionTrace

    s = SessionLocal()
    beall = s.get(AdminAgentSetting, 1)
    elotte = (beall.kill_switch, beall.kill_switch_indok)
    utolso_nyom = s.scalar(select(func.max(ActionTrace.id))) or 0
    h = {"Authorization": f"Bearer {create_access_token('2', 'admin')}"}
    c = TestClient(app)
    try:
        r = c.post("/api/v1/admin-agent/pause", headers=h, json={"indok": "teszt"})
        assert r.status_code == 200 and r.json()["kill_switch"] is True
        # Minden futtató/módosító kérés áll…
        for ut, body in (
            ("/api/v1/admin-agent/self-check", None),
            ("/api/v1/admin-agent/learning-runs", None),
            ("/api/v1/admin-agent/mail-learning/run", None),
            ("/api/v1/admin-agent/tasks", {"tipus": "szamla", "cim": "x"}),
        ):
            r = c.post(ut, headers=h, json=body)
            assert r.status_code == 423 and "le van állítva" in r.json()["detail"], ut
        assert c.patch("/api/v1/admin-agent/settings", headers=h, json={"module_enabled": True}).status_code == 423
        # …az ütemezett feladatok sem futnak…
        for feladat in (admin_agent_tasks.observer_task, admin_agent_tasks.self_check_task,
                        admin_agent_tasks.nightly_distill_task, admin_agent_tasks.weekly_eval_task,
                        admin_agent_tasks.levelezes_task):
            assert feladat() == {"leallitva": True}
        # …de a tudás olvasható marad.
        for ut in ("/api/v1/admin-agent/memory", "/api/v1/admin-agent/rules", "/api/v1/admin-agent/knowledge-graph",
                   "/api/v1/admin-agent/mail-learning"):
            assert c.get(ut, headers=h).status_code == 200, ut
        assert c.get("/api/v1/admin-agent/settings", headers=h).json()["kill_switch"] is True

        r = c.post("/api/v1/admin-agent/resume", headers=h)
        assert r.status_code == 200 and r.json()["kill_switch"] is False
        # Visszakapcsolva: az utalás mint feladattípus már nem létezik.
        r = c.post("/api/v1/admin-agent/tasks", headers=h, json={"tipus": "utalas", "cim": "Utalás teszt"})
        assert r.status_code == 400
    finally:
        s.rollback()
        beall = s.get(AdminAgentSetting, 1)
        beall.kill_switch, beall.kill_switch_indok = elotte
        # A leállítás/visszakapcsolás naplóbejegyzése is a teszté volt.
        naplo = s.scalars(
            select(ActionTrace.muvelet).where(ActionTrace.id > utolso_nyom, ActionTrace.eroforras == "lara")
        ).all()
        assert set(naplo) == {"veszleallitas", "visszakapcsolas"}
        s.execute(delete(ActionTrace).where(ActionTrace.id > utolso_nyom, ActionTrace.eroforras == "lara"))
        s.commit()
        s.close()


def test_utalas_nem_feladattipus_es_nem_tema():
    from app.admin_agent.enums import TaskType
    from app.admin_agent.tudashalo import TEMAK

    assert "utalas" not in {t.value for t in TaskType}
    assert "utalas" not in TEMAK
