"""Lara személyiség-rétege: verzió, profilok, prompt-sorrend, állapot-mondatok,
stílusőr. Determinisztikus — modellhívás nincs. A DB-s részek (verzió-kapcsoló,
megszólítás) Postgres nélkül self-skip; tranzakció a végén rollback."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.admin_agent import szemelyiseg as sz


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
    from app.models.employee import Employee

    e = db.get(Employee, 2)
    if e is None:
        pytest.skip("Nincs admin munkatárs (#2) a teszthez.")
    return e


def test_a_szemelyiseg_egy_verziozott_forrasbol_jon():
    """A B rész szövege egy fájlból jön; a forrás-megjegyzés nem kerül a modell elé."""
    s = sz.szemelyiseg("v1")
    assert s.startswith("#") or s[:1].isalpha()
    assert "<!--" not in s
    assert "Lara" in s
    # Ismeretlen verzió → alapverzió, nem üres személyiség.
    assert sz.szemelyiseg("nincs-ilyen") == s


def test_ugyfel_profil_elokeszitve_de_kikapcsolva(db, admin):
    assert sz.PROFILOK["ugyfel"].engedelyezve is False
    with pytest.raises(sz.ProfilHiba):
        sz.kontextus(db, admin, profil="ugyfel")
    with pytest.raises(sz.ProfilHiba):
        sz.kontextus(db, admin, profil="nincs")
    k = sz.kontextus(db, admin)
    assert k.audience == "internal" and k.profil == "belso" and k.locale == "hu"


def test_prompt_sorrend_biztonsag_feladat_kontextus_szemelyiseg(db, admin):
    k = sz.kontextus(db, admin, jogosultsagok=["view"])
    p = sz.rendszer_prompt(k, "FELADAT-JEL", biztonsag="BIZTONSAG-JEL")
    i_b, i_f, i_k, i_sz = (
        p.index("BIZTONSAG-JEL"), p.index("FELADAT-JEL"), p.index("HITELES KONTEXTUS"), p.index("LARA SZEMÉLYISÉGE"),
    )
    assert i_b < i_f < i_k < i_sz
    assert "Emoji: soha" in p


def test_megszolitas_csak_a_mentett_preferenciabol(db, admin):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    lim = dict(s.limitek or {})
    lim.pop("megszolitasok", None)
    s.limitek = lim
    db.flush()
    assert sz.kontextus(db, admin).verified_display_name is None
    s.limitek = {**lim, "megszolitasok": {str(admin.id): "Teszt (demó)"}}
    db.flush()
    assert sz.kontextus(db, admin).verified_display_name == "Teszt (demó)"


def test_verzio_kapcsolo_es_visszaallas(db):
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    s.limitek = {**(s.limitek or {}), "szemelyiseg_verzio": "v999"}
    db.flush()
    assert sz.aktiv_verzio(db) == sz.ALAP_VERZIO
    s.limitek = {**(s.limitek or {}), "szemelyiseg_verzio": "v1"}
    db.flush()
    assert sz.aktiv_verzio(db) == "v1"


def test_allapot_mondatok_egyertelmuek():
    assert sz.allapot_mondat("piszkozat", "a levél") == "Elkészítettem a piszkozatot (a levél). Még nem küldtem el."
    assert "jóváhagyásod" in sz.allapot_mondat("jovahagyasra_var", "a számla-besorolás")
    assert "nem indítom újra" in sz.allapot_mondat("bizonytalan", "A küldés").lower()
    with pytest.raises(KeyError):
        sz.allapot_mondat("nincs", "x")


def test_stilusor_emoji_sablon_hamis_vegrehajtas_tiltott_nev():
    s, j = sz.stilusor("Szuper kérdés! 😀 A számla a HYPE-001 projektkódra megy.")
    assert s == "A számla a HYPE-001 projektkódra megy."
    assert "emoji_torolve" in j and any(x.startswith("sablon_nyitas_torolve") for x in j)

    _, j = sz.stilusor("Rendben, elküldtem a partnernek.")
    assert "hamis_vegrehajtas_gyanu:elküldtem" in j
    _, j = sz.stilusor("Rendben, elküldtem a partnernek.", csak_olvaso=False)
    assert not any(x.startswith("hamis_vegrehajtas") for x in j)

    _, j = sz.stilusor("Az ágens szerint ez így jó.")
    assert "tiltott_nev" in j
    _, j = sz.stilusor("Miben segíthetek még?")
    assert "tiltott_fordulat:miben segíthetek még" in j


def test_modell_nelkuli_valasz_tenyszeru():
    assert "nem érhető el" in sz.modell_nelkuli_valasz([])
    v = sz.modell_nelkuli_valasz(["A szabály: X partner → működési."])
    assert "– A szabály: X partner → működési." in v
