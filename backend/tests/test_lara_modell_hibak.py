"""Lara beszélgetése a modell hibáinál (2026-09): újrapróbálás átmeneti
hibánál, biztonságos mód elutasított beállításnál, eszköz nélküli kör hibás
eszközhívás / üres válasz után, zárókör a lépéskorlátnál, és a konkrét ok a
tartalék-válaszban. Valódi modellhívás nincs: a Gemini-kliens hamis."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from google import genai
from google.genai import errors

from app.admin_agent import nyomozas as ny
from app.admin_agent import szemelyiseg as sz
from app.core.config import settings


def _hiba(kod: int, uzenet: str = "hiba") -> errors.APIError:
    osztaly = errors.ClientError if kod < 500 else errors.ServerError
    return osztaly(kod, {"error": {"code": kod, "message": uzenet, "status": "X"}})


def _valasz(szoveg: str | None = "", ok: str = "STOP", hivasok=None):
    jelolt = SimpleNamespace(content=SimpleNamespace(role="model", parts=[]), finish_reason=SimpleNamespace(name=ok))
    return SimpleNamespace(function_calls=hivasok, text=szoveg, candidates=[jelolt], prompt_feedback=None)


@pytest.fixture()
def hamis(monkeypatch):
    """A Gemini-kliens hamis: a `korok` sorból ad választ vagy dob hibát;
    a `konfigok` a hívások beállításait gyűjti."""
    allapot = SimpleNamespace(korok=[], konfigok=[], alvasok=[])

    class _Modellek:
        def generate_content(self, model, contents, config):
            allapot.konfigok.append(config)
            k = allapot.korok.pop(0)
            if isinstance(k, Exception):
                raise k
            return k

    monkeypatch.setattr(genai, "Client", lambda api_key=None: SimpleNamespace(models=_Modellek()))
    monkeypatch.setattr(settings, "gemini_api_key", "teszt-kulcs")
    monkeypatch.setattr(settings, "gemini_model", "gemini-2.5-flash")
    monkeypatch.setattr(ny.time, "sleep", lambda s: allapot.alvasok.append(s))
    return allapot


def test_atmeneti_hibanal_varakozik_es_ujraprobal(hamis):
    hamis.korok = [_hiba(429), _hiba(503), _valasz("Kész válasz.")]
    hivas, szoveg = ny._Gemini("r", "k", [], 16384).lepes()
    assert hivas == [] and szoveg == "Kész válasz."
    assert hamis.alvasok == list(ny.UJRAPROBA_VARAKOZAS)


def test_tartos_atmeneti_hiba_tovabbdobodik(hamis):
    hamis.korok = [_hiba(429)] * (len(ny.UJRAPROBA_VARAKOZAS) + 1)
    with pytest.raises(errors.APIError):
        ny._Gemini("r", "k", [], 16384).lepes()


def test_elutasitott_beallitasnal_biztonsagos_mod(hamis):
    hamis.korok = [_hiba(400, "max_output_tokens is out of supported range"), _valasz("Rendben.")]
    g = ny._Gemini("r", "k", [], 16384)
    assert g.lepes() == ([], "Rendben.")
    elso, masodik = hamis.konfigok
    assert elso.thinking_config is not None and elso.max_output_tokens == 16384
    assert g.biztonsagos and masodik.thinking_config is None and masodik.max_output_tokens == 8192


def test_hibas_eszkozhivas_utan_eszkoz_nelkuli_kor(hamis):
    hamis.korok = [_valasz("", "MALFORMED_FUNCTION_CALL"), _valasz("A válasz eszköz nélkül.")]
    g = ny._Gemini("r", "k", [], 16384)
    assert g.lepes() == ([], "A válasz eszköz nélkül.")
    masodik = hamis.konfigok[1]
    assert masodik.tool_config.function_calling_config.mode.name == "NONE"
    assert g._contents[-1].parts[0].text == ny.ESZKOZ_NELKUL_KERES


def test_tartosan_ures_valasz_modellvalasz_hiba(hamis):
    hamis.korok = [_valasz("", "MALFORMED_FUNCTION_CALL"), _valasz("", "STOP")]
    with pytest.raises(ny.ModellValaszHiba) as e:
        ny._Gemini("r", "k", [], 16384).lepes()
    assert "üres választ" in str(e.value)


def test_biztonsagi_szuro_nem_probalkozik_ujra(hamis):
    r = _valasz("", "SAFETY")
    hamis.korok = [r]
    with pytest.raises(ny.ModellValaszHiba) as e:
        ny._Gemini("r", "k", [], 16384).lepes()
    assert "SAFETY" in str(e.value) and len(hamis.konfigok) == 1


def test_hiba_leiras_osztalyoz_es_nem_szivarogtat_kulcsot():
    assert "kvóta" in ny.hiba_leiras(_hiba(429))
    assert "túlterhelt" in ny.hiba_leiras(_hiba(503))
    assert "kulcs" in ny.hiba_leiras(_hiba(403))
    assert "GEMINI_MODEL" in ny.hiba_leiras(_hiba(404))
    l400 = ny.hiba_leiras(_hiba(400, "bad request key=AIzaSyTITKOS12345678"))
    assert "(400)" in l400 and "AIzaSyTITKOS12345678" not in l400
    assert "időtúllépés" in ny.hiba_leiras(TimeoutError("timed out"))


def test_kimeneti_korlat_es_json_tisztitas():
    assert ny.kimeneti_korlat("gemini-2.5-flash", 16384) == 16384
    assert ny.kimeneti_korlat("gemini-2.0-flash", 16384) == 8192
    assert ny.kimeneti_korlat("gemini-3-pro", 100000) == 65536
    assert ny._jsonba({"d": date(2026, 9, 1), "o": Decimal("12.5")}) == {"d": "2026-09-01", "o": "12.5"}


def test_eszkozhurok_hibanal_a_lepesekben_a_konkret_ok(monkeypatch):
    class _Dob:
        def lepes(self):
            raise _hiba(404)

        def eredmenyek(self, parok):
            pass

    ny.teszt_beszelgetes(lambda *_: _Dob())
    try:
        vegso, lepesek, allapot = ny.eszkozhurok(None, None, "r", "f")
    finally:
        ny.teszt_beszelgetes(None)
    assert allapot == "hiba" and vegso == ""
    assert lepesek[-1]["hiba"] and "nem található" in lepesek[-1]["cel"]


def test_lepeskorlatnal_zarokor_valaszt_ad(monkeypatch):
    class _Vegtelen:
        def lepes(self):
            return [("ismeretlen_eszkoz", {})], None

        def eredmenyek(self, parok):
            pass

        def zaras(self):
            return "Összegyűjtött válasz."

    monkeypatch.setattr(ny, "MAX_LEPES", 2)
    ny.teszt_beszelgetes(lambda *_: _Vegtelen())
    try:
        vegso, lepesek, allapot = ny.eszkozhurok(None, None, "r", "f")
    finally:
        ny.teszt_beszelgetes(None)
    assert allapot == "kesz" and vegso == "Összegyűjtött válasz."


def test_hiba_tartalek_kimondja_az_okot():
    s = sz.hiba_tartalek("a modell-szolgáltatás túl sok kérést kapott (429)", ["Szabály: X"])
    assert "429" in s and "– Szabály: X" in s and "nem érhető el" not in s
    assert sz.hiba_tartalek(None, []).startswith("A válasz elkészítése most nem sikerült.")
    assert sz.stilusor(s, csak_olvaso=True)[0]  # a stílusőr nem nyeli el


def test_modell_ellenorzes_kulcs_nelkul(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    e = ny.modell_ellenorzes()
    assert e["ok"] is False and "GEMINI_API_KEY" in e["hiba"]


def test_modell_ellenorzes_lepesenkent(hamis):
    hamis.korok = [_valasz("rendben"), _hiba(400, "Function calling is not enabled for this model")]
    e = ny.modell_ellenorzes()
    assert e["ok"] is False and e["modell"] == "gemini-2.5-flash"
    assert e["lepesek"][0]["ok"] and e["lepesek"][0]["valasz"] == "rendben"
    assert not e["lepesek"][1]["ok"] and "(400)" in e["lepesek"][1]["hiba"]
