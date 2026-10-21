"""Lara beállítások és bizalmi szint feloldása, plus a policy-döntés
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


#: A vészleállítás üzenete: minden felületen és válaszban ugyanez.
LEALLITVA_UZENET = (
    "Lara le van állítva (vészleállítás). A tudása megmaradt; "
    "a Beállítások → „Lara visszakapcsolása” gombbal indítható újra."
)


def leallitva(db: Session | None = None) -> bool:
    """Le van-e állítva Lara (vészleállítás)?

    A vészleállítás TELJES leállás: se ütemezett feladat (megfigyelés, tanulás,
    önellenőrzés, levelezés-olvasás, értékelés), se kézi indítás, se elemzés,
    se végrehajtás. A tudás (szabályok, példák, kérdések) NEM törlődik, és a
    kapcsolók (modul, mellékhatás, források) állása is megmarad - a
    visszakapcsolás pontosan oda tér vissza.

    `db` nélkül (vagy hosszú futás közben) FRISS munkamenetből olvas, hogy egy
    másik folyamatban közben bekapcsolt vészleállítást is azonnal lássa."""
    if db is not None:
        s = db.get(AdminAgentSetting, 1)
        return bool(s and s.kill_switch)
    from app.core.database import SessionLocal

    friss = SessionLocal()
    try:
        return bool(friss.scalar(select(AdminAgentSetting.kill_switch).where(AdminAgentSetting.id == 1)))
    finally:
        friss.close()


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


# ── Lara felelőse (egyetlen címzett) ─────────────────────────────────────────
#
# A felhasználó kérése: Laránál MINDENÉRT egy ember, Vidor Gergely a felelős -
# minden feladat hozzá tartozik, minden ellenőrzés/jóváhagyás/kérdés/összesítő
# hozzá fut be, és egyelőre MÁSNAK Lara semmit nem küld. A felelős a
# Beállításokban átállítható (`limitek.felelos_employee_id`); ha nincs
# beállítva, név szerint keressük meg. A „csak a felelősnek" mód
# (`limitek.csak_felelosnek`, alap: be) kapcsolja ki a többi címzettet.

#: Alapértelmezett felelős — név szerint (ékezet/sorrend nem számít).
ALAP_FELELOS_NEV = "Vidor Gergely"


def _nev_kulcs(nev: str | None) -> frozenset[str]:
    import unicodedata

    s = unicodedata.normalize("NFKD", (nev or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return frozenset(t for t in "".join(c if c.isalnum() else " " for c in s).split() if t)


def csak_felelosnek(db: Session) -> bool:
    """Minden Lara-értesítés/jóváhagyás csak a felelősé (alap: igen)."""
    return (get_settings(db).limitek or {}).get("csak_felelosnek") is not False


def lara_felelos(db: Session):
    """Lara felelőse (aktív munkatárs) — a beállított, vagy név szerint az
    alapértelmezett. None, ha nem található (ilyenkor Lara NEM küld senkinek)."""
    from app.models.employee import Employee

    fid = (get_settings(db).limitek or {}).get("felelos_employee_id")
    if isinstance(fid, int):
        e = db.get(Employee, fid)
        if e is not None and e.is_active:
            return e
    kulcs = _nev_kulcs(ALAP_FELELOS_NEV)
    for e in db.scalars(select(Employee).where(Employee.is_active.is_(True))).all():
        if _nev_kulcs(e.full_name) == kulcs:
            return e
    return None
