"""Admin-Ágens — auditált végrehajtó réteg (jóváhagyott javaslat → művelet).

A végrehajtás EGYETLEN útja. A sorrend (master prompt 8.): javaslat →
(már megtörtént determinista validálás) → policy-ellenőrzés → jóváhagyás
kötése → idempotens lefoglalás → ISMÉTELT jogosultság-/verzió-/vészleállítás-/
approval-ellenőrzés → eszközművelet → eredmény → audit.

Kulcsgaranciák:
* A policy engine (settings_service.resolve_decision) minden úton érvényesül,
  a végrehajtás pillanatában olvasva a kapcsolókat (nem korábbi pillanatképből).
* A jóváhagyás a KONKRÉT javaslat payload-hash-éhez kötött; ha a javaslatot
  újabb váltotta le (superseded) vagy a hash eltér, a régi jóváhagyással nem
  indítható művelet (új jóváhagyás kell).
* Idempotencia: javaslatonként egyetlen végrehajtási rekord (egyedi kulcs),
  így dupla kattintás / két worker / retry mellett sem lesz dupla mellékhatás.
* Fencing token: lejárt lease-ű worker nem írhat felül újabb tulajdonost.
* Mellékhatás CSAK akkor fut, ha a policy AUTO/engedélyezett és a globális
  kapcsolók (modul + mellékhatás) engedik; egyébként a rekord `blocked`, és az
  eszköz nem hívódik meg (biztonságos alapállás).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.enums import (
    ActorKind,
    ApprovalState,
    ExecutionState,
    ProposalState,
    RiskClass,
    TaskState,
)
from app.admin_agent.policy import Decision
from app.admin_agent.settings_service import resolve_decision
from app.models.admin_agent import (
    ActionExecution,
    ActionProposal,
    ActionTrace,
    AdminTask,
    Approval,
)
from app.models.employee import Employee


class VegrehajtasHiba(Exception):
    """A végrehajtás nem indítható (elévült jóváhagyás, hash-eltérés, tiltás)."""

    def __init__(self, ok: str):
        self.ok = ok
        super().__init__(ok)


@dataclass(frozen=True)
class ToolSpec:
    """Egy regisztrált, szűk hatókörű eszköz. A `run` VÉGZI a tényleges
    mellékhatást — csak akkor hívjuk, ha a policy és a kapcsolók engedik."""

    eszkoz: str
    risk: RiskClass
    tipus: str
    run: Callable[[Session, ActionProposal, AdminTask, Employee], dict]


def _most() -> datetime:
    return datetime.now(timezone.utc)


# ── Eszköztár (regisztrált eszközök) ────────────────────────────────────────
# Szándékosan szűk: általános SQL/shell/URL nincs. Új eszköz ide, deklarált
# kockázattal és feladattípussal kerül.

def _run_szamla_jovahagy(db: Session, proposal: ActionProposal, task: AdminTask, user: Employee) -> dict:
    """A meglévő pénzügyi szolgáltatáson át rögzíti a kiadást. CSAK a végrehajtó
    guard-lánc után, engedélyezett mellékhatás mellett hívódik."""
    from app.models.bejovo_szamla import BejovoSzamla
    from app.services import szamla_erkeztetes

    ref = (task.forras_referenciak or {}).get("bejovo_szamla_id")
    if ref is None:
        raise VegrehajtasHiba("Hiányzik a beérkező számla hivatkozása.")
    bejovo = db.get(BejovoSzamla, int(ref))
    if bejovo is None:
        raise VegrehajtasHiba("A beérkező számla nem található.")
    naplo = szamla_erkeztetes.jovahagy(db, bejovo, user, dict(proposal.payload))
    return {"rogzites_naplo": naplo, "rogzitett_expense_id": bejovo.rogzitett_expense_id}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "szamla_erkeztetes.jovahagy": ToolSpec(
        eszkoz="szamla_erkeztetes.jovahagy",
        risk=RiskClass.R2,
        tipus="szamla",
        run=_run_szamla_jovahagy,
    ),
}


def _idempotencia_kulcs(proposal: ActionProposal) -> str:
    #: Javaslatonként EGY végrehajtás. Az egyedi DB-megszorítás garantálja, hogy
    #: párhuzamos hívásból is csak egy rekord jön létre.
    return f"proposal:{proposal.id}"


def _audit(db: Session, task_id: int | None, muvelet: str, eroforras: str | None, eredmeny: str, diff: dict) -> None:
    db.add(
        ActionTrace(
            task_id=task_id,
            szereplo=ActorKind.SYSTEM.value,
            muvelet=muvelet,
            eroforras=eroforras,
            diff=diff,
            eredmeny=eredmeny,
            tortent_at=_most(),
        )
    )


def execute_approved(
    db: Session,
    approval: Approval,
    *,
    approver: Employee,
    fencing_token: int | None = None,
) -> ActionExecution:
    """Egy jóváhagyott javaslat végrehajtása a teljes guard-lánccal. A hívó
    commitál. Mindig ActionExecution-t ad vissza (állapota mondja meg, mi
    történt); tiltásnál/hibánál nem dob, hanem a rekordban jelzi."""
    proposal = db.get(ActionProposal, approval.proposal_id)
    if proposal is None:
        raise VegrehajtasHiba("A javaslat nem található.")
    task = db.get(AdminTask, proposal.task_id)

    kulcs = _idempotencia_kulcs(proposal)

    def _blokk(ok: str) -> ActionExecution:
        ex = _execution_lefoglal(db, proposal, approval, kulcs, fencing_token)
        if ex.allapot == ExecutionState.SUCCEEDED.value:
            return ex  # már sikeresen lefutott — nem bántjuk
        ex.allapot = ExecutionState.FAILED.value
        ex.eredmeny = {"blokk_ok": ok}
        _audit(db, proposal.task_id, "vegrehajtas_blokkolt", proposal.eszkoz, "blocked", {"ok": ok})
        return ex

    # 1) Jóváhagyás kötése a KONKRÉT javaslat-hash-hez.
    if approval.allapot not in (ApprovalState.APPROVED.value,):
        return _blokk(f"A jóváhagyás nincs jóváhagyott állapotban ({approval.allapot}).")
    if approval.felhasznalt_at is not None or approval.allapot == ApprovalState.CONSUMED.value:
        return _blokk("A jóváhagyás már fel lett használva.")
    if approval.payload_hash != proposal.payload_hash:
        return _blokk("A jóváhagyás elavult: a javaslat időközben megváltozott — új jóváhagyás kell.")
    if approval.lejar_at is not None and approval.lejar_at < _most():
        return _blokk("A jóváhagyás lejárt.")

    # 2) Javaslat frissessége.
    if proposal.allapot not in (ProposalState.READY.value,):
        return _blokk(f"A javaslat nem hajtható végre ebben az állapotban ({proposal.allapot}).")
    if proposal.lejar_at is not None and proposal.lejar_at < _most():
        return _blokk("A javaslat lejárt.")

    # 3) Regisztrált eszköz.
    spec = TOOL_REGISTRY.get(proposal.eszkoz)
    if spec is None:
        return _blokk(f"Ismeretlen/nem regisztrált eszköz: {proposal.eszkoz}.")

    # 4) Policy ÚJRA, a végrehajtás pillanatában (modul/mellékhatás/kill/trust).
    dontes = resolve_decision(db, risk=spec.risk, tipus=spec.tipus, altipus=(task.altipus if task else None))
    if dontes.decision is Decision.BLOCKED:
        # Kill-switch, modul ki, mellékhatás tiltva, L0 vagy R3 → nem fut.
        return _blokk(dontes.reason)
    # NEEDS_APPROVAL: a most kötött, érvényes jóváhagyás elégíti ki. AUTO: mehet.

    # 5) Idempotens lefoglalás.
    ex = _execution_lefoglal(db, proposal, approval, kulcs, fencing_token)
    if ex.allapot == ExecutionState.SUCCEEDED.value:
        return ex  # egy másik hívás már végrehajtotta

    # 6) Fencing: lejárt lease-ű (kisebb tokenű) worker nem folytathatja.
    if fencing_token is not None and ex.fencing_token is not None and fencing_token < ex.fencing_token:
        ex.allapot = ExecutionState.FAILED.value
        ex.eredmeny = {"blokk_ok": "Elavult worker (fencing token)."}
        return ex

    # 7) Eszközművelet (VALÓDI mellékhatás).
    ex.allapot = ExecutionState.RUNNING.value
    ex.probalkozasok = (ex.probalkozasok or 0) + 1
    try:
        eredmeny = spec.run(db, proposal, task, approver)
    except Exception as exc:  # noqa: BLE001 — a hibát rögzítjük, nem nyeljük el csendben
        ex.allapot = ExecutionState.FAILED.value
        ex.eredmeny = {"hiba": str(exc)}
        if task is not None:
            task.allapot = TaskState.FAILED.value
            task.utolso_hiba = str(exc)
        _audit(db, proposal.task_id, "vegrehajtas_hiba", proposal.eszkoz, "failed", {"hiba": str(exc)})
        return ex

    # 8) Siker → audit, állapotok lezárása, jóváhagyás felhasználva.
    ex.allapot = ExecutionState.SUCCEEDED.value
    ex.eredmeny = eredmeny
    proposal.allapot = ProposalState.CONSUMED.value
    approval.allapot = ApprovalState.CONSUMED.value
    approval.felhasznalt_at = _most()
    if task is not None:
        task.allapot = TaskState.COMPLETED.value
        task.befejezve_at = _most()
        task.row_version += 1
    _audit(db, proposal.task_id, "vegrehajtva", proposal.eszkoz, "succeeded", {"execution_id": ex.id})
    return ex


def _execution_lefoglal(
    db: Session,
    proposal: ActionProposal,
    approval: Approval,
    kulcs: str,
    fencing_token: int | None,
) -> ActionExecution:
    """Idempotens végrehajtási rekord: az egyedi kulcs miatt párhuzamos hívásból
    is EGY rekord marad. Ütközéskor a meglévőt adjuk vissza."""
    letezo = db.scalar(select(ActionExecution).where(ActionExecution.idempotencia_kulcs == kulcs))
    if letezo is not None:
        return letezo
    ex = ActionExecution(
        proposal_id=proposal.id,
        approval_id=approval.id,
        idempotencia_kulcs=kulcs,
        allapot=ExecutionState.PENDING.value,
        probalkozasok=0,
        fencing_token=fencing_token,
    )
    db.add(ex)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        meglevo = db.scalar(select(ActionExecution).where(ActionExecution.idempotencia_kulcs == kulcs))
        if meglevo is None:
            raise
        return meglevo
    return ex
