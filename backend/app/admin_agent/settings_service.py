"""HYRON beállítások és bizalmi szint feloldása, plus a policy-döntés
összeállítása. Ez a modul köti össze az adatbázis-beli kapcsolókat és
trust-policy sorokat a policy engine-nel (policy.decide)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import RiskClass, TrustLevel
from app.admin_agent.policy import DecisionResult, PolicyInputs, decide
from app.models.admin_agent import AdminAgentSetting, TrustPolicy


def get_settings(db: Session) -> AdminAgentSetting:
    """A singleton beállítás-sor (id=1). Ha valamiért hiányzik, biztonságos
    alapállással hozzuk létre."""
    s = db.get(AdminAgentSetting, 1)
    if s is None:
        s = AdminAgentSetting(id=1, module_enabled=False, side_effects_enabled=False, kill_switch=False)
        db.add(s)
        db.flush()
    return s


def get_trust(db: Session, tipus: str, altipus: str | None) -> tuple[TrustLevel, frozenset[str]]:
    """Az adott feladattípus×altípus bizalmi szintje és az L3+-hoz auto-ra
    engedélyezett R2 altípusok. Először pontos (tipus, altipus), majd a
    típus-alap (altipus IS NULL), végül L0."""
    sorok = db.scalars(select(TrustPolicy).where(TrustPolicy.tipus == tipus)).all()
    pontos = next((r for r in sorok if r.altipus == altipus), None)
    alap = next((r for r in sorok if r.altipus is None), None)
    valasztott = pontos or alap
    if valasztott is None:
        return TrustLevel.L0, frozenset()
    try:
        szint = TrustLevel(valasztott.szint)
    except ValueError:
        szint = TrustLevel.L0
    engedett = frozenset(valasztott.auto_engedett_altipusok or [])
    return szint, engedett


def resolve_decision(db: Session, *, risk: RiskClass, tipus: str, altipus: str | None) -> DecisionResult:
    """A végrehajtási döntés összeállítása a beállításokból és a trust-policyból.

    Ezt KELL hívni minden mellékhatásos lépés előtt (a policy engine az egyetlen
    döntéshozó). A vészleállítást/modul-kapcsolót itt, a döntés pillanatában
    olvassuk ki - nem egy korábbi pillanatképből."""
    s = get_settings(db)
    trust, auto_altipusok = get_trust(db, tipus, altipus)
    return decide(
        PolicyInputs(
            risk=risk,
            trust=trust,
            module_enabled=s.module_enabled,
            side_effects_enabled=s.side_effects_enabled,
            kill_switch_active=s.kill_switch,
            subtype=altipus,
            auto_allowed_subtypes=auto_altipusok,
        )
    )
