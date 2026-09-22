"""Admin-Ágens policy engine: a végrehajtási döntés EGYETLEN, szerveroldali
helye. Minden hívási útnak (worker, közvetlen API, újrapróbálás) ezen kell
átmennie egy mellékhatásos lépés előtt.

A döntést a KOCKÁZAT (szerveroldali besorolás), a BIZALMI szint
(feladattípus×altípus), a modul/mellékhatás kapcsolók és a VÉSZLEÁLLÍTÁS
együtt határozzák meg. A magasabb bizalmi szint SOSEM írhatja felül az
R3-tiltást. A modell nem befolyásolja ezt a döntést."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from app.admin_agent.enums import RISK_ORDER, TRUST_ORDER, RiskClass, TrustLevel


class Decision(str, Enum):
    BLOCKED = "blocked"  # nem hajtható végre (most)
    NEEDS_APPROVAL = "needs_approval"  # emberi jóváhagyás kell
    AUTO = "auto"  # engedélyezett automatikus végrehajtás


@dataclass(frozen=True)
class PolicyInputs:
    risk: RiskClass
    trust: TrustLevel
    module_enabled: bool
    side_effects_enabled: bool
    kill_switch_active: bool
    #: A feladat altípusa (pl. "beérkezési_visszajelzés") - az R2 auto csak
    #: kifejezetten engedélyezett, alacsony kockázatú altípusra mehet.
    subtype: str | None = None
    #: Az adott feladattípushoz L3+ trust mellett auto-ra engedélyezett R2
    #: altípusok (alapból üres → R2 mindig jóváhagyás-köteles).
    auto_allowed_subtypes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reason: str


def decide(inp: PolicyInputs) -> DecisionResult:
    """A végrehajtási döntés. Fail-closed: kétség esetén szigorúbb."""
    # 1) R3 sosem engedélyezhető - bármi is a bizalmi szint.
    if inp.risk == RiskClass.R3:
        return DecisionResult(Decision.BLOCKED, "R3 tiltott művelet (pl. banki végrehajtás).")

    # 2) R0 (olvasás / belső javaslat): nincs mellékhatás, mindig mehet.
    if inp.risk == RiskClass.R0:
        return DecisionResult(Decision.AUTO, "R0 belső/olvasó művelet, nincs mellékhatás.")

    # Innentől R1/R2 = mellékhatásos. Előbb a globális kapuk.
    if inp.kill_switch_active:
        return DecisionResult(Decision.BLOCKED, "Vészleállítás aktív.")
    if not inp.module_enabled:
        return DecisionResult(Decision.BLOCKED, "Az Admin-Ágens modul ki van kapcsolva.")
    if not inp.side_effects_enabled:
        return DecisionResult(Decision.BLOCKED, "A mellékhatásos végrehajtás globálisan tiltva.")

    # 3) L0 (árnyék): semmilyen üzleti/külső mellékhatás.
    if inp.trust == TrustLevel.L0:
        return DecisionResult(Decision.BLOCKED, "L0 árnyék-mód: nincs mellékhatásos végrehajtás.")

    # 4) R1 (ellenőrzötten visszafordítható belső írás).
    if inp.risk == RiskClass.R1:
        if TRUST_ORDER[inp.trust] >= TRUST_ORDER[TrustLevel.L2]:
            return DecisionResult(Decision.AUTO, "R1 belső írás, L2+ bizalom: automatikus.")
        return DecisionResult(Decision.NEEDS_APPROVAL, "R1 belső írás L1-en: emberi véglegesítés kell.")

    # 5) R2 (külső kommunikáció vagy pénzügyi/jogi jelentőségű változás).
    #    Alapból jóváhagyás-köteles; auto CSAK L3+ ÉS kifejezetten engedélyezett,
    #    alacsony kockázatú altípus esetén.
    if inp.risk == RiskClass.R2:
        auto_ok = (
            TRUST_ORDER[inp.trust] >= TRUST_ORDER[TrustLevel.L3]
            and inp.subtype is not None
            and inp.subtype in inp.auto_allowed_subtypes
        )
        if auto_ok:
            return DecisionResult(Decision.AUTO, "R2 engedélyezett altípus, L3+ bizalom: automatikus.")
        return DecisionResult(Decision.NEEDS_APPROVAL, "R2 külső/pénzügyi-jogi művelet: emberi jóváhagyás kell.")

    # Ismeretlen kockázat → fail-closed.
    return DecisionResult(Decision.BLOCKED, "Ismeretlen kockázati besorolás.")


def max_risk(risks: Iterable[RiskClass]) -> RiskClass:
    """Több művelet legmagasabb kockázata (a jóváhagyás mindig a legszigorúbbra)."""
    legmagasabb = RiskClass.R0
    for r in risks:
        if RISK_ORDER[r] > RISK_ORDER[legmagasabb]:
            legmagasabb = r
    return legmagasabb
