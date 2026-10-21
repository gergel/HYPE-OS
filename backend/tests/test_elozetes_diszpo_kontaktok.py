"""Az előzetes diszpó levele a projekt KONTAKTOK mezőjét is viszi (a
felhasználó kérése), hogy a stáb már ekkor tudjon egyeztetni."""

from types import SimpleNamespace

from app.services import dispo


def _html(kontaktok: str | None) -> str:
    return dispo._PRE_DISPO_HTML.format(
        helyszin="Kapolcs (demó)",
        kontaktok_blokk=dispo._kontaktok_blokk(SimpleNamespace(kontaktok=kontaktok)),
        diszpo_szoveg="08:00 gyülekező (demó)",
    )


def test_kontaktok_benne_vannak_es_escapelve():
    html = _html("Kiss Anna (demó) +36 30 123 4567 <anna@example.com>")
    assert "Kontaktok:" in html
    assert "Kiss Anna (demó) +36 30 123 4567 &lt;anna@example.com&gt;" in html
    # A helyszín után, a diszpó szövege előtt.
    assert html.index("Kapolcs") < html.index("Kontaktok:") < html.index("08:00 gyülekező")


def test_ures_kontaktok_nem_jelenik_meg():
    assert "Kontaktok:" not in _html(None)
    assert "Kontaktok:" not in _html("   ")
