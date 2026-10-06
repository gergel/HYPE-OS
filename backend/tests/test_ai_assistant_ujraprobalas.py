"""AI Assistant (a felhasználó jelzése, 2026-10: a feladatok többször
megakadtak a "503 UNAVAILABLE - high demand" üzenettel): átmeneti
Gemini-hibánál ugyanaz a kérés ugyanazzal a modellel újrapróbálódik, a
várakozás látszik a naplóban, a Leállítás közben is hat, és ha végleg nem
megy, a válasz felsorolja az eddigi lépéseket és "folytasd"-ra továbbvihető.

Hamis Gemini-klienssel, tranzakcióban fut, a végén VISSZAGÖRGETŐDIK."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.ai_beszelgetes import AiBeszelgetes, AiUzenet
from app.models.employee import Employee, EmployeeType, SystemRole
from app.services import ai_assistant


def _tulterhelt():
    return genai_errors.ServerError(
        503, {"error": {"code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE"}}
    )


def _szoveges(szoveg: str):
    return SimpleNamespace(function_calls=[], text=szoveg, candidates=[])


def _keres(szoveg: str):
    hivas = types.FunctionCall(name="globalis_kereses", args={"szoveg": szoveg})
    return SimpleNamespace(
        function_calls=[hivas],
        text=None,
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=[types.Part(function_call=hivas)]))],
    )


class _HamisKliens:
    """A `valaszok` sorban: kivétel (dobja) vagy válasz (adja); kifogyva 503."""

    def __init__(self, valaszok, mellekhatas=None):
        self.valaszok = list(valaszok)
        self.hivasok = 0
        self.mellekhatas = mellekhatas
        self.models = self

    def generate_content(self, **_kw):
        self.hivasok += 1
        if self.mellekhatas:
            self.mellekhatas(self.hivasok)
        v = self.valaszok.pop(0) if self.valaszok else _tulterhelt()
        if isinstance(v, Exception):
            raise v
        return v


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


@pytest.fixture
def kor(db, monkeypatch):
    admin = Employee(full_name="AI Admin (demó)", tipus=EmployeeType.BELSOS, email="ai-ujra-demo@example.test",
                     role=SystemRole.ADMIN, is_active=True)
    db.add(admin)
    db.flush()
    b = AiBeszelgetes(employee_id=admin.id, cim="teszt (demó)", fut=True, leallitas_kert=False)
    db.add(b)
    db.flush()
    db.add(AiUzenet(beszelgetes_id=b.id, szerep="felhasznalo", szoveg="keresd meg a demó projektet"))
    db.flush()
    monkeypatch.setattr(settings, "gemini_api_key", "teszt-kulcs")
    alvasok: list[float] = []
    monkeypatch.setattr(ai_assistant.time, "sleep", lambda mp: alvasok.append(mp))

    def futtat(kliens):
        monkeypatch.setattr(ai_assistant.genai, "Client", lambda **_kw: kliens)
        ai_assistant.futtat(db, admin, b, "keresd meg a demó projektet")
        return db.scalars(select(AiUzenet).where(AiUzenet.beszelgetes_id == b.id).order_by(AiUzenet.id)).all()

    return SimpleNamespace(db=db, admin=admin, b=b, futtat=futtat, alvasok=alvasok)


def test_atmeneti_503_utan_ujraprobal_es_sikerul(kor):
    kliens = _HamisKliens([_tulterhelt(), _tulterhelt(), _szoveges("Kész, megvan.")])
    uzenetek = kor.futtat(kliens)
    assert kliens.hivasok == 3
    esemenyek = [u.szoveg for u in uzenetek if u.szerep == "esemeny"]
    assert len([e for e in esemenyek if "újrapróbálom" in e]) == 2
    assert "(1/5)" in esemenyek[0] and "503" in esemenyek[0]
    assert uzenetek[-1].szerep == "asszisztens" and uzenetek[-1].szoveg == "Kész, megvan."
    # 3 + 6 mp várakozás, másodpercenként (hogy a Leállítás közben is hasson).
    assert len(kor.alvasok) == 9


def test_vegleges_tulterheles_folytathato_valaszt_ad(kor):
    kliens = _HamisKliens([_keres("Nem létező projekt (demó)")])
    uzenetek = kor.futtat(kliens)
    assert kliens.hivasok == 1 + 1 + len(ai_assistant.UJRAPROBA_VARAKOZAS)
    vege = uzenetek[-1]
    assert vege.szerep == "asszisztens"
    assert "megszakadt" in vege.szoveg and "folytasd" in vege.szoveg
    assert "Keresek a rendszerben: „Nem létező projekt (demó)”" in vege.szoveg
    # A nyers API-válasz (JSON) nem kerül a felhasználó elé.
    assert "{'error'" not in vege.szoveg


def test_leallitas_a_varakozas_kozben(kor):
    def leallit(_n):
        kor.db.execute(AiBeszelgetes.__table__.update().where(AiBeszelgetes.id == kor.b.id).values(leallitas_kert=True))

    kliens = _HamisKliens([], mellekhatas=leallit)
    uzenetek = kor.futtat(kliens)
    assert kliens.hivasok == 1
    assert uzenetek[-1].szoveg.startswith("Leállítottam")


def test_nem_atmeneti_hiba_nem_probalkozik_ujra(kor):
    hibas = genai_errors.ClientError(400, {"error": {"code": 400, "message": "rossz kérés", "status": "INVALID_ARGUMENT"}})
    kliens = _HamisKliens([hibas])
    uzenetek = kor.futtat(kliens)
    assert kliens.hivasok == 1
    assert not [u for u in uzenetek if u.szerep == "esemeny" and "újrapróbálom" in (u.szoveg or "")]
    assert "API-hibát" in uzenetek[-1].szoveg


def test_ask_is_ujraprobal(kor, monkeypatch):
    kliens = _HamisKliens([_tulterhelt(), _szoveges("Válasz.")])
    monkeypatch.setattr(ai_assistant.genai, "Client", lambda **_kw: kliens)
    assert ai_assistant.ask(kor.db, kor.admin, "kérdés") == "Válasz."
    assert kliens.hivasok == 2 and kor.alvasok == [3]
