"""Lara — auditált végrehajtó réteg (jóváhagyott javaslat → művelet).

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
    ADMIN_FELADATTIPUSOK,
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
    mellékhatást — csak akkor hívjuk, ha a policy és a kapcsolók engedik.

    A `validate` determinista, szerver-oldali ellenőrzés (a modell NEM válthatja
    ki): a hiányosságok listáját adja vissza; nem üres → a javaslat nem
    hajtható végre (jóváhagyás mellett sem). A `side_effect` jelzi, hogy a `run`
    üzleti/külső mellékhatással jár (audit + kockázati kommunikáció miatt)."""

    eszkoz: str
    cim: str
    risk: RiskClass
    tipus: str
    run: Callable[[Session, ActionProposal, AdminTask, Employee], dict]
    side_effect: bool = True
    validate: Callable[[dict], list[str]] | None = None


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


# Automatikus / nem válaszolható feladók — ezekre SOHA nem küldünk választ
# (körkörös automata-hurok, bounce, out-of-office elleni védelem, master prompt 10.).
_AUTOMATA_MINTAK = (
    "no-reply",
    "noreply",
    "no_reply",
    "do-not-reply",
    "donotreply",
    "mailer-daemon",
    "mailerdaemon",
    "postmaster",
    "bounce",
    "notifications@",
    "automated",
)


def _email_automatikus_cimzett(cim: str) -> bool:
    c = (cim or "").strip().lower()
    return any(minta in c for minta in _AUTOMATA_MINTAK)


def _validate_email_valasz(payload: dict) -> list[str]:
    """Determinista, szerver-oldali ellenőrzés az e-mail-küldés előtt. A
    hiányosságok/tiltások listája; nem üres → nem küldhető."""
    hibak: list[str] = []
    cimzettek = payload.get("to") or []
    if isinstance(cimzettek, str):
        cimzettek = [cimzettek]
    if not cimzettek:
        hibak.append("Nincs címzett.")
    for c in cimzettek:
        if not isinstance(c, str) or "@" not in c:
            hibak.append(f"Érvénytelen címzett: {c!r}.")
        elif _email_automatikus_cimzett(c):
            # Körkörös automata-hurok elleni védelem: automata feladóra nem
            # válaszolunk (master prompt 10./21.).
            hibak.append(f"Automatikus/nem válaszolható címre nem küldünk levelet: {c}.")
    if not (payload.get("subject") or "").strip():
        hibak.append("Hiányzik a tárgy.")
    if not (payload.get("html_body") or payload.get("body") or "").strip():
        hibak.append("Hiányzik a levél szövege.")
    return hibak


def _run_email_valasz_kuldes(db: Session, proposal: ActionProposal, task: AdminTask, user: Employee) -> dict:
    """E-mail (válasz) kiküldése a MEGLÉVŐ google_email szolgáltatáson át. Ha a
    Gmail nincs beállítva, a szolgáltatás beszédes hibát dob → a végrehajtás
    FAILED lesz „Beállítás szükséges" indokkal (NEM hamis siker)."""
    from app.services import google_email

    p = proposal.payload
    cimzettek = p.get("to") or []
    if isinstance(cimzettek, str):
        cimzettek = [cimzettek]
    thread_id, message_id, rfc822 = google_email.send_message(
        list(cimzettek),
        str(p.get("subject") or ""),
        str(p.get("html_body") or p.get("body") or ""),
        thread_id=p.get("thread_id"),
        in_reply_to=p.get("in_reply_to"),
        extra_cc=p.get("cc"),
    )
    return {"gmail_thread_id": thread_id, "gmail_message_id": message_id, "rfc822_message_id": rfc822}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "szamla_erkeztetes.jovahagy": ToolSpec(
        eszkoz="szamla_erkeztetes.jovahagy",
        cim="Számla felvezetése kiadásként",
        risk=RiskClass.R2,
        tipus="szamla",
        run=_run_szamla_jovahagy,
        side_effect=True,
    ),
    "email.valasz_kuldes": ToolSpec(
        eszkoz="email.valasz_kuldes",
        cim="E-mail válasz kiküldése",
        risk=RiskClass.R2,
        tipus="email",
        run=_run_email_valasz_kuldes,
        side_effect=True,
        validate=_validate_email_valasz,
    ),
}

# TIG / szerződés PISZKOZAT mentése a meglévő úton ("Készítés alatt", PDF és
# kiküldés NÉLKÜL). R1: belső, visszafordítható írás — a kiküldés/aláírás
# továbbra is emberi lépés a meglévő felületen.
from app.admin_agent.tervezo import piszkozat_mentes_futtato, validate_tervezet  # noqa: E402

TOOL_REGISTRY["tig.piszkozat_mentes"] = ToolSpec(
    eszkoz="tig.piszkozat_mentes",
    cim="TIG-piszkozat(ok) mentése (kiküldés nélkül)",
    risk=RiskClass.R1,
    tipus="tig",
    run=piszkozat_mentes_futtato("tig"),
    side_effect=True,
    validate=validate_tervezet("tig"),
)
TOOL_REGISTRY["szerzodes.piszkozat_mentes"] = ToolSpec(
    eszkoz="szerzodes.piszkozat_mentes",
    cim="Szerződés-piszkozat(ok) mentése (kiküldés nélkül)",
    risk=RiskClass.R1,
    tipus="szerzodes",
    run=piszkozat_mentes_futtato("szerzodes"),
    side_effect=True,
    validate=validate_tervezet("szerzodes"),
)

# FONTOS: banki utalást INDÍTÓ/aláíró/végrehajtó eszköz SZÁNDÉKOSAN NINCS
# regisztrálva (master prompt 10./8.: R3, tiltott), és utalás-előkészítés sincs:
# az utalással Lara nem foglalkozik - a kifizetendőket a Pénzügyek „Utalásra
# váró számlák" listája mutatja.


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
    # 3a) HATÁSKÖR: Lara csak adminisztrációs feladatot végezhet (a rendszer
    #     többi részét csak figyeli és tanul belőle).
    if spec.tipus not in ADMIN_FELADATTIPUSOK or (task is not None and task.tipus not in ADMIN_FELADATTIPUSOK):
        return _blokk("Lara csak adminisztrációs feladatot végezhet (számla, TIG, szerződés, adminisztrációs e-mail).")

    # 3b) Determinista validálás ÚJRA a végrehajtás előtt (a payload időközben
    #     nem változott, de a szabály lehet, hogy szigorodott — fail-closed).
    if spec.validate is not None:
        hianyok = spec.validate(dict(proposal.payload))
        if hianyok:
            return _blokk("A javaslat nem valid: " + "; ".join(hianyok))

    # 4) Policy ÚJRA, a végrehajtás pillanatában (modul/mellékhatás/kill/trust).
    dontes = resolve_decision(db, risk=spec.risk, tipus=spec.tipus, altipus=(task.altipus if task else None))
    if dontes.decision is Decision.BLOCKED:
        # Kill-switch, modul ki, mellékhatás tiltva, L0 vagy R3 → nem fut.
        return _blokk(dontes.reason)
    # NEEDS_APPROVAL: a most kötött, érvényes jóváhagyás elégíti ki. AUTO: mehet.

    # 4b) „Csak a felelősnek" mód (a felhasználó kérése: egyelőre Lara MÁSNAK
    #     semmit nem küld): kimenő levél csak a felelős saját címére mehet, és
    #     javaslatot csak a felelős hagyhat jóvá.
    from app.admin_agent.settings_service import csak_felelosnek, lara_felelos

    if csak_felelosnek(db):
        felelos = lara_felelos(db)
        if felelos is None or approver.id != felelos.id:
            return _blokk("Lara javaslatairól jelenleg csak a felelőse dönthet.")
        if spec.tipus == "email":
            p = dict(proposal.payload)
            cimek = []
            for mezo in ("to", "cc", "bcc"):
                v = p.get(mezo) or []
                cimek += [v] if isinstance(v, str) else list(v)
            sajat = (felelos.email or "").strip().lower()
            idegen = [c for c in cimek if str(c).strip().lower() != sajat]
            if idegen or not sajat:
                return _blokk(
                    "Lara jelenleg csak a felelősének küldhet levelet — más címzett ("
                    + ", ".join(map(str, idegen or cimek)) + ") nem engedélyezett."
                )

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


def _hataskor_ellenorzes() -> None:
    """Betöltéskor: az eszköz-regiszterben csak adminisztrációs eszköz lehet —
    egy más területre ható eszköz felvétele már az indításnál hibát ad."""
    rossz = [e for e, spec in TOOL_REGISTRY.items() if spec.tipus not in ADMIN_FELADATTIPUSOK]
    if rossz:
        raise RuntimeError(f"Lara csak adminisztrációs eszközt kaphat; nem az: {', '.join(rossz)}")


_hataskor_ellenorzes()
