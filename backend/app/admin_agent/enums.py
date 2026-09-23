"""Lara: állapotgépek, kockázati és bizalmi szintek.

Szöveges (str) enumok, hogy az adatbázisban és az API-ban is olvashatók
legyenek, és a meglévő HYPE OS mintát kövessék (a state mezők String-ek).
A kockázatot MINDIG a szerver sorolja be (lásd policy.py) - a modell nem
minősítheti át saját műveletét alacsonyabbra."""

from __future__ import annotations

from enum import Enum


class TaskType(str, Enum):
    """A modul üzleti feladattípusai + egy általános/egyéb.

    UTALÁS NINCS (a felhasználó döntése): Lara utalni soha nem fog, és az
    utalás-előkészítés sem az ő dolga - hogy mi utalható, azt a Pénzügyek
    „Utalásra váró számlák" listája mutatja."""

    SZAMLA = "szamla"  # számla-felvezetés
    EMAIL = "email"  # e-mail-válasz
    TIG = "tig"  # teljesítésigazolás előkészítés
    SZERZODES = "szerzodes"  # szerződés előkészítés
    EGYEB = "egyeb"


class TaskState(str, Enum):
    """A feladat szerveroldali állapotgépe (master prompt 7. pont)."""

    NEW = "new"
    ANALYZING = "analyzing"
    NEEDS_INFO = "needs_info"
    PROPOSAL_READY = "proposal_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: A feladat lezárt állapotai - ezekből érdemi munka már nincs.
LEZART_TASK_STATES = frozenset(
    {TaskState.COMPLETED, TaskState.REJECTED, TaskState.CANCELLED}
)


class AgentRunState(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProposalState(str, Enum):
    DRAFT = "draft"  # elkészült, de még nem véglegesített javaslat
    READY = "ready"  # validált, immutable payload + hash
    SUPERSEDED = "superseded"  # újabb javaslat váltotta le
    EXPIRED = "expired"
    CONSUMED = "consumed"  # végrehajtás már felhasználta


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"  # egy jóváhagyás EGY végrehajtásra használható fel


class ExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    #: Külső küldés timeoutja után, ha nem tudható, megtörtént-e: egyeztetés kell.
    UNKNOWN = "execution_unknown"
    RECONCILED = "reconciled"


class ActorKind(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class CorrectionType(str, Enum):
    """A javítás jellege - a tanulás ezt eltérően kezeli."""

    EGYSZERI_KIVETEL = "egyszeri_kivetel"  # egyedi eset, nem szabályosít
    STILUS = "stilus"  # stílus/hangnem javítás
    TENYSZERU_HIBA = "tenyszeru_hiba"  # tárgyi tévedés (ez a legerősebb jel)
    UJ_UZLETI_ADAT = "uj_uzleti_adat"  # nem korrekció: új tény
    BESOROLANDO = "besorolando"  # kétes: emberi besorolásra vár


class RuleState(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"  # gépi javaslat, emberi jóváhagyásra vár
    ACTIVE = "active"
    RETIRED = "retired"


class RiskClass(str, Enum):
    """SZERVEROLDALI kockázati besorolás (a modell nem írhatja át).

    R0 olvasás / belső javaslat
    R1 ellenőrzötten visszafordítható belső írás
    R2 külső kommunikáció VAGY pénzügyi/jogi jelentőségű változás
    R3 tiltott (pl. banki végrehajtás) - sosem engedélyezhető
    """

    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


#: Rendezés az összehasonlításhoz (magasabb = kockázatosabb).
RISK_ORDER = {RiskClass.R0: 0, RiskClass.R1: 1, RiskClass.R2: 2, RiskClass.R3: 3}


class TrustLevel(str, Enum):
    """Bizalmi szint feladattípus×altípus szinten (master prompt 12. pont).

    L0 árnyék · L1 előkészítés+emberi véglegesítés · L2 szűk auto ·
    L3 munkasor-önállóság kivételkezeléssel · L4 csak külön engedélyezett szűk kör.
    """

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


TRUST_ORDER = {
    TrustLevel.L0: 0,
    TrustLevel.L1: 1,
    TrustLevel.L2: 2,
    TrustLevel.L3: 3,
    TrustLevel.L4: 4,
}
