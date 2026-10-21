"""A kimenő SZERZŐDÉS- és TIG-levelek aláírása (a felhasználó kérése,
2026-10): Rahman Martin mellett Berta Zsóka is szerepeljen - és mindegyik
levél ugyanazt a közös aláírást használja (google_email.ADMIN_ALAIRAS_HTML)."""

from __future__ import annotations

import pytest

from app.api.routes import internal_performance_certificates, performance_certificates, subcontractor_contracts
from app.services import keretszerzodes_kuldes, szerzodes_emlekezteto
from app.services.google_email import ADMIN_ALAIRAS_HTML

LEVELEK = {
    "alvállalkozói szerződés": subcontractor_contracts._CONTRACT_EMAIL_HTML,
    "szerződés-emlékeztető": szerzodes_emlekezteto.EMLEKEZTETO_HTML,
    "külsős TIG": performance_certificates._TIG_EMAIL_HTML.format(projektdatum="2026.10.07."),
    "belsős TIG": internal_performance_certificates._BELSOS_TIG_EMAIL_HTML.format(nev="Teszt", honap="2026. október"),
    "keretszerződés": keretszerzodes_kuldes.EMAIL_HTML,
}


def test_az_alairasban_martin_es_zsoka_is_ott_van():
    for szoveg in ("HYPE PRODUCTIONS - ADMINISZTRÁCIÓ", "Hype Productions Kft.",
                   "Rahman Martin - cégvezető", "martin.rahman@hypestab.hu", "+36 30 898 7600",
                   "Berta Zsóka - back office manager", "zsoka.berta@hypestab.hu", "+36 30 342 5431"):
        assert szoveg in ADMIN_ALAIRAS_HTML


@pytest.mark.parametrize("nev", list(LEVELEK))
def test_minden_szerzodes_es_tig_level_a_kozos_alairassal_megy(nev):
    level = LEVELEK[nev]
    assert ADMIN_ALAIRAS_HTML in level, nev
    assert level.count("Rahman Martin") == 1, nev
