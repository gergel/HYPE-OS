"""Admin-Ágens — általános javaslatkészítő (bármely regisztrált eszközre).

A `pipeline_szamla` a beérkező számlából származtatja a payloadot; ez az általános
út akkor kell, amikor a payload már adott (pl. e-mail-válasz, amit ember vagy
később a modell fogalmaz meg). A biztonsági lánc ugyanaz: determinista validálás
→ integráció-ellenőrzés → policy engine → javaslat + (szükség szerint) jóváhagyás.
A tényleges végrehajtás továbbra is a `executor.execute_approved` guard-láncán megy.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.admin_agent.enums import (
    ActorKind,
    AgentRunState,
    ApprovalState,
    ProposalState,
    TaskState,
)
from app.admin_agent.executor import TOOL_REGISTRY
from app.admin_agent.integrations import eszkoz_elerheto
from app.admin_agent.policy import Decision, DecisionResult
from app.admin_agent.settings_service import resolve_decision
from app.models.admin_agent import (
    ActionProposal,
    ActionTrace,
    AdminTask,
    AgentRun,
    Approval,
)


class JavaslatHiba(ValueError):
    pass


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def keszit_javaslat(
    db: Session,
    task: AdminTask,
    *,
    eszkoz: str,
    payload: dict,
    trigger: str = "manual",
) -> tuple[ActionProposal, DecisionResult]:
    """Javaslat készítése egy feladathoz egy regisztrált eszközre. A hívó
    commitál. Determinista validálás + integráció-ellenőrzés → a hiányos vagy
    nem konfigurált javaslat DRAFT és nem hajtható végre; a valid javaslat READY,
    és a policy szerint (NEEDS_APPROVAL) jóváhagyás is készül hozzá."""
    spec = TOOL_REGISTRY.get(eszkoz)
    if spec is None:
        raise JavaslatHiba(f"Ismeretlen/nem regisztrált eszköz: {eszkoz}")

    run = AgentRun(
        task_id=task.id,
        trigger=trigger,
        allapot=AgentRunState.RUNNING.value,
        provider="kezi",  # a payloadot ember/kliens adta; az érték-hozzáadás a guard-lánc
        kezdes_at=_most(),
        terv={"lepes": "keszit_javaslat", "eszkoz": eszkoz},
    )
    db.add(run)
    db.flush()

    hianyok = list(spec.validate(payload)) if spec.validate else []
    elerheto, indok = eszkoz_elerheto(eszkoz)
    if not elerheto and indok:
        hianyok.append(indok)  # „Beállítás szükséges" — a javaslat nem véglegesíthető
    ellenorzesek = {"rendben": not hianyok, "hianyok": hianyok, "integracio_ok": elerheto}

    db.add(
        ActionTrace(
            task_id=task.id,
            run_id=run.id,
            szereplo=ActorKind.AGENT.value,
            muvelet="javaslat_keszites",
            eroforras=eszkoz,
            diff={"ellenorzesek": ellenorzesek},
            eredmeny="rendben" if not hianyok else "hianyos",
            tortent_at=_most(),
        )
    )

    dontes = resolve_decision(db, risk=spec.risk, tipus=spec.tipus, altipus=task.altipus)

    proposal = ActionProposal(
        task_id=task.id,
        run_id=run.id,
        eszkoz=eszkoz,
        payload=payload,
        payload_hash=_hash(payload),
        kockazat=spec.risk.value,
        ellenorzesek=ellenorzesek,
        allapot=ProposalState.READY.value if not hianyok else ProposalState.DRAFT.value,
    )
    db.add(proposal)
    db.flush()

    db.add(
        ActionTrace(
            task_id=task.id,
            run_id=run.id,
            szereplo=ActorKind.SYSTEM.value,
            muvelet="policy_dontes",
            eroforras=eszkoz,
            diff={"decision": dontes.decision.value, "reason": dontes.reason, "kockazat": spec.risk.value},
            eredmeny=dontes.decision.value,
            tortent_at=_most(),
        )
    )

    # Feladatállapot + (szükség szerint) jóváhagyás.
    if hianyok:
        task.allapot = TaskState.NEEDS_INFO.value
        task.blokkolo_ok = "; ".join(hianyok)
    elif dontes.decision is Decision.NEEDS_APPROVAL:
        task.allapot = TaskState.AWAITING_APPROVAL.value
        task.blokkolo_ok = None
        db.add(
            Approval(
                proposal_id=proposal.id,
                payload_hash=proposal.payload_hash,
                allapot=ApprovalState.PENDING.value,
            )
        )
    elif dontes.decision is Decision.AUTO:
        task.allapot = TaskState.QUEUED.value
        task.blokkolo_ok = None
    else:  # BLOCKED (árnyék / kapcsoló ki)
        task.allapot = TaskState.PROPOSAL_READY.value
        task.blokkolo_ok = dontes.reason

    task.kockazat = spec.risk.value
    task.row_version += 1
    run.allapot = AgentRunState.SUCCEEDED.value
    run.veg_at = _most()
    return proposal, dontes
