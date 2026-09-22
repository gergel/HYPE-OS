"""Admin-Ágens policy engine (biztonságkritikus döntéslogika) egységtesztjei.

Tiszta függvények, külső függőség nélkül futtatható. A mátrix rögzíti a
biztonságos alapállás és a bizalmi rámpa invariánsait (master prompt 8., 12.).
"""

from app.admin_agent.enums import RiskClass, TrustLevel
from app.admin_agent.policy import Decision, PolicyInputs, decide, max_risk


def _p(risk, trust, *, mod=True, se=True, kill=False, sub=None, allow=frozenset()):
    return PolicyInputs(
        risk=risk,
        trust=trust,
        module_enabled=mod,
        side_effects_enabled=se,
        kill_switch_active=kill,
        subtype=sub,
        auto_allowed_subtypes=allow,
    )


def test_r3_mindig_blokkolt():
    for szint in TrustLevel:
        assert decide(_p(RiskClass.R3, szint)).decision is Decision.BLOCKED


def test_r0_mindig_auto():
    # R0 = olvasás/belső javaslat: nincs mellékhatás, a kapcsolóktól függetlenül mehet.
    assert decide(_p(RiskClass.R0, TrustLevel.L0, mod=False, se=False, kill=True)).decision is Decision.AUTO


def test_l0_arnyek_blokkol_minden_mellekhatast():
    assert decide(_p(RiskClass.R1, TrustLevel.L0)).decision is Decision.BLOCKED
    assert decide(_p(RiskClass.R2, TrustLevel.L0)).decision is Decision.BLOCKED


def test_r1_bizalmi_rampa():
    assert decide(_p(RiskClass.R1, TrustLevel.L1)).decision is Decision.NEEDS_APPROVAL
    assert decide(_p(RiskClass.R1, TrustLevel.L2)).decision is Decision.AUTO
    assert decide(_p(RiskClass.R1, TrustLevel.L3)).decision is Decision.AUTO


def test_r2_alapbol_jovahagyas_koteles():
    for szint in (TrustLevel.L1, TrustLevel.L2, TrustLevel.L3, TrustLevel.L4):
        assert decide(_p(RiskClass.R2, szint)).decision is Decision.NEEDS_APPROVAL


def test_r2_auto_csak_l3_es_allowlistelt_altipus():
    # L2 + allowlist: még mindig jóváhagyás (nem elég magas a bizalom).
    assert decide(_p(RiskClass.R2, TrustLevel.L2, sub="x", allow=frozenset({"x"}))).decision is Decision.NEEDS_APPROVAL
    # L3 + allowlistelt altípus: auto.
    assert decide(_p(RiskClass.R2, TrustLevel.L3, sub="x", allow=frozenset({"x"}))).decision is Decision.AUTO
    # L3 + NEM allowlistelt altípus: jóváhagyás.
    assert decide(_p(RiskClass.R2, TrustLevel.L3, sub="y", allow=frozenset({"x"}))).decision is Decision.NEEDS_APPROVAL


def test_globalis_kapuk_blokkolnak():
    assert decide(_p(RiskClass.R1, TrustLevel.L2, mod=False)).decision is Decision.BLOCKED
    assert decide(_p(RiskClass.R1, TrustLevel.L2, se=False)).decision is Decision.BLOCKED
    assert decide(_p(RiskClass.R1, TrustLevel.L2, kill=True)).decision is Decision.BLOCKED


def test_max_risk():
    assert max_risk([RiskClass.R0, RiskClass.R2, RiskClass.R1]) is RiskClass.R2
    assert max_risk([RiskClass.R0]) is RiskClass.R0
    assert max_risk([]) is RiskClass.R0
