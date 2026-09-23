"""Lara API (Fázis B/C alap). Az `/admin-agent` oldal jogosultságával.

BIZTONSÁGOS ALAPÁLLÁS: ezek a végpontok NEM hajtanak végre üzleti/külső
mellékhatást (L0). A task-létrehozás és -szerkesztés belső munkaszervezés; a
jóváhagyás-döntés csak rögzül (a végrehajtó réteg a következő fázis). Minden
mellékhatásos végrehajtás a policy engine-en (admin_agent.policy) fog átmenni.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin_agent.enums import (
    LEZART_TASK_STATES,
    ApprovalState,
    CorrectionType,
    TaskState,
    TaskType,
)
from app.admin_agent.enums import RuleState, TrustLevel
from app.admin_agent.evals import run_eval, safety_esetek_magveto
from app.admin_agent.executor import TOOL_REGISTRY, execute_approved
from app.admin_agent.integrations import integracio_allapotok
from app.admin_agent.learning import distill
from app.admin_agent.observer import FELRETEVE, korszak_rendezes, megfigyeles, tanulas_kezdete_datum
from app.admin_agent.pipeline_szamla import arnyek_elemzes
from app.admin_agent.proposals import JavaslatHiba, keszit_javaslat
from app.admin_agent.settings_service import (
    LEALLITVA_UZENET,
    csak_felelosnek,
    get_settings,
    lara_felelos,
    leallitva,
)
from app.core.database import get_db
from app.core.security import Role, check_page_action, require_page_action
from app.models.admin_agent import (
    ActionExecution,
    ActionProposal,
    ActionTrace,
    AdminTask,
    AgentRelease,
    AgentRun,
    Approval,
    Correction,
    EvalCase,
    EvalRun,
    LaraKerdes,
    LearningRun,
    MemoryChunk,
    PlaybookRule,
    SourceEvent,
    TrustPolicy,
)
from app.models.bejovo_szamla import BejovoSzamla
from app.models.employee import Employee

def _nem_leallitva(request: Request, db: Session = Depends(get_db)) -> None:
    """VÉSZLEÁLLÍTÁS: leállított Laránál semmilyen módosító/futtató kérés nem
    megy át (elemzés, tervezet, jóváhagyás, végrehajtás, tanulás, önellenőrzés,
    levelezés, beállítás) - csak a leállítás és a visszakapcsolás. Olvasni
    (tudás, napló, beállítások) továbbra is lehet: a tudás megmarad."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.url.path.rstrip("/").endswith(("/pause", "/resume")):
        return
    if leallitva(db):
        raise HTTPException(status_code=423, detail=LEALLITVA_UZENET)


router = APIRouter(prefix="/admin-agent", tags=["admin-agent"], dependencies=[Depends(_nem_leallitva)])

PAGE = "/admin-agent"
_MINDEN_SZEREPKOR = tuple(Role)

_TIPUS_ERTEKEK = {t.value for t in TaskType}
_ALLAPOT_ERTEKEK = {s.value for s in TaskState}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _task_sor(t: AdminTask) -> dict:
    return {
        "id": t.id,
        "tipus": t.tipus,
        "altipus": t.altipus,
        "cim": t.cim,
        "osszefoglalo": t.osszefoglalo,
        "allapot": t.allapot,
        "prioritas": t.prioritas,
        "kockazat": t.kockazat,
        "uncertainty": t.uncertainty,
        "trust_level": t.trust_level,
        "felelos_id": t.felelos_id,
        "hatarido": t.hatarido.isoformat() if t.hatarido else None,
        "project_id": t.project_id,
        "project_code_id": t.project_code_id,
        "client_id": t.client_id,
        "partner_nev": t.partner_nev,
        "blokkolo_ok": t.blokkolo_ok,
        "utolso_hiba": t.utolso_hiba,
        "row_version": t.row_version,
        "letrehozva": t.created_at.isoformat() if t.created_at else None,
        "befejezve_at": t.befejezve_at.isoformat() if t.befejezve_at else None,
    }


# ── Áttekintés ────────────────────────────────────────────────────────────────


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Áttekintő aggregátumok. Ahol még nincs elég adat, a mező null és a
    felület "Még nincs elég adat"-ot mutat (nem hamis nulla)."""
    s = get_settings(db)
    most = _most()
    nyitott = db.scalar(
        select(func.count(AdminTask.id)).where(AdminTask.allapot.notin_([x.value for x in LEZART_TASK_STATES]))
    ) or 0
    lejart = db.scalar(
        select(func.count(AdminTask.id)).where(
            AdminTask.hatarido.is_not(None),
            AdminTask.hatarido < most,
            AdminTask.allapot.notin_([x.value for x in LEZART_TASK_STATES]),
        )
    ) or 0
    varakozo_jovahagyas = db.scalar(
        select(func.count(Approval.id)).where(Approval.allapot == "pending")
    ) or 0
    # Állapot szerinti bontás.
    allapot_bontas = {
        allapot: (db.scalar(select(func.count(AdminTask.id)).where(AdminTask.allapot == allapot)) or 0)
        for allapot in _ALLAPOT_ERTEKEK
    }
    return {
        "modul": {
            "engedelyezve": s.module_enabled,
            "mellekhatas_engedelyezve": s.side_effects_enabled,
            "veszleallitas": s.kill_switch,
        },
        "nyitott": nyitott,
        "lejart": lejart,
        "varakozo_jovahagyas": varakozo_jovahagyas,
        "allapot_bontas": allapot_bontas,
        "integraciok": integracio_allapotok(),
        # A tanulás látható állapota: mennyit figyelt meg / tanult / mi vár jóváhagyásra.
        "tanulas": {
            "megfigyeles_bekapcsolva": bool((s.engedett_forrasok or {}).get("megfigyeles")),
            "megfigyelt_lepesek": db.scalar(
                select(func.count(SourceEvent.id)).where(SourceEvent.forras == "megfigyeles")
            ) or 0,
            "javitasok": db.scalar(select(func.count(Correction.id))) or 0,
            "szabaly_jeloltek": db.scalar(
                select(func.count(PlaybookRule.id)).where(PlaybookRule.allapot.in_(["pending", "draft"]))
            ) or 0,
            "aktiv_szabalyok": db.scalar(
                select(func.count(PlaybookRule.id)).where(PlaybookRule.allapot == "active")
            ) or 0,
            "pelda_jeloltek": db.scalar(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.tanulasi_halmaz == "jovahagyott",
                    MemoryChunk.ervenyes.is_(False),
                    MemoryChunk.visszavont.is_(False),
                    MemoryChunk.minosites != FELRETEVE,
                )
            ) or 0,
            "felretett_regi_jeloltek": db.scalar(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.ervenyes.is_(False),
                    MemoryChunk.visszavont.is_(False),
                    MemoryChunk.minosites == FELRETEVE,
                )
            ) or 0,
            "tanulas_kezdete": tanulas_kezdete_datum(db).isoformat(),
            "nyitott_kerdesek": db.scalar(
                select(func.count(LaraKerdes.id)).where(LaraKerdes.allapot == "nyitott")
            ) or 0,
            "jovahagyott_peldak": db.scalar(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.tanulasi_halmaz == "jovahagyott",
                    MemoryChunk.ervenyes.is_(True),
                    MemoryChunk.visszavont.is_(False),
                )
            ) or 0,
        },
        # Mért mutatók: még nincs elég adat (a mérőrendszer a Tanulás/eval fázis).
        "ember_nelkul_lezart": None,
        "elfogadasi_arany": None,
        "kritikus_hibak": None,
        "modell_koltseg_mikro": None,
        "eleg_adat": False,
    }


# ── Munkasor ──────────────────────────────────────────────────────────────────


@router.get("/tasks")
def tasks_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
    tipus: str | None = Query(default=None),
    allapot: str | None = Query(default=None),
    felelos_id: int | None = Query(default=None),
    project_code_id: int | None = Query(default=None),
    lejart: bool = Query(default=False),
    kereses: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    felt = []
    if tipus:
        felt.append(AdminTask.tipus == tipus)
    if allapot:
        felt.append(AdminTask.allapot == allapot)
    if felelos_id is not None:
        felt.append(AdminTask.felelos_id == felelos_id)
    if project_code_id is not None:
        felt.append(AdminTask.project_code_id == project_code_id)
    if lejart:
        felt.append(AdminTask.hatarido.is_not(None))
        felt.append(AdminTask.hatarido < _most())
        felt.append(AdminTask.allapot.notin_([x.value for x in LEZART_TASK_STATES]))
    if kereses and kereses.strip():
        minta = f"%{kereses.strip()}%"
        felt.append(AdminTask.cim.ilike(minta) | AdminTask.partner_nev.ilike(minta))
    ossz = db.scalar(select(func.count(AdminTask.id)).where(*felt)) or 0
    sorok = db.scalars(
        select(AdminTask).where(*felt).order_by(AdminTask.prioritas.desc(), AdminTask.id.desc()).limit(limit).offset(offset)
    ).all()
    return {"osszesen": ossz, "elemek": [_task_sor(t) for t in sorok]}


class TaskCreateIn(BaseModel):
    tipus: str = Field(min_length=1)
    altipus: str | None = None
    cim: str = Field(min_length=1, max_length=300)
    osszefoglalo: str | None = None
    prioritas: int = 0
    felelos_id: int | None = None
    hatarido: str | None = None
    project_code_id: int | None = None
    partner_nev: str | None = None


def _uj_feladat_felelose(db: Session, kert: int | None) -> int | None:
    if csak_felelosnek(db):
        f = lara_felelos(db)
        if f is not None:
            return f.id
    return kert


@router.post("/tasks")
def task_letrehozas(
    payload: TaskCreateIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    if payload.tipus not in _TIPUS_ERTEKEK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen feladattípus: {payload.tipus}")
    hatarido = None
    if payload.hatarido:
        try:
            hatarido = datetime.fromisoformat(payload.hatarido.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Érvénytelen határidő.") from exc
    t = AdminTask(
        tipus=payload.tipus,
        altipus=payload.altipus,
        cim=payload.cim.strip(),
        osszefoglalo=payload.osszefoglalo,
        allapot=TaskState.NEW.value,
        prioritas=payload.prioritas,
        # „Csak a felelősnek" módban minden Lara-feladat felelőse Lara felelőse.
        felelos_id=_uj_feladat_felelose(db, payload.felelos_id),
        hatarido=hatarido,
        project_code_id=payload.project_code_id,
        partner_nev=(payload.partner_nev or "").strip() or None,
        trust_level="L0",
    )
    db.add(t)
    db.commit()
    return _task_sor(t)


@router.post("/tasks/from-bejovo/{bejovo_id}")
def task_bejovo_szamlabol(
    bejovo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """L0 ÁRNYÉK-ELEMZÉS egy beérkező számlára. Nem hajt végre üzleti/külső
    műveletet: Lara csak elemez és javaslatot rögzít a policy engine
    döntésével. A tényleges rögzítés továbbra is a meglévő érkeztető-folyamaton,
    emberi jóváhagyással történik (lásd services/szamla_erkeztetes.jovahagy).
    Idempotens: ugyanarra a számlára ugyanabban az állapotban nem duplikál."""
    bejovo = db.get(BejovoSzamla, bejovo_id)
    if bejovo is None:
        raise HTTPException(status_code=404, detail="A beérkező számla nem található.")
    t = arnyek_elemzes(db, bejovo, trigger="manual")
    db.commit()
    return _task_sor(t)


@router.get("/tasks/{task_id}")
def task_reszletek(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    return _task_sor(t)


@router.get("/tasks/{task_id}/timeline")
def task_idovonal(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A feladat teljes, olvasható idővonala: Lara-futások, nyomvonal-
    bejegyzések (ki mit tett, milyen eredménnyel) és a művelet-javaslatok a
    payloaddal. Kizárólag olvasás — semmit nem hajt végre."""
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    runs = db.scalars(select(AgentRun).where(AgentRun.task_id == task_id).order_by(AgentRun.id)).all()
    traces = db.scalars(
        select(ActionTrace).where(ActionTrace.task_id == task_id).order_by(ActionTrace.tortent_at, ActionTrace.id)
    ).all()
    proposals = db.scalars(
        select(ActionProposal).where(ActionProposal.task_id == task_id).order_by(ActionProposal.id.desc())
    ).all()
    prop_ids = [p.id for p in proposals]
    approvals = (
        db.scalars(select(Approval).where(Approval.proposal_id.in_(prop_ids))).all() if prop_ids else []
    )
    approval_allapot = {a.proposal_id: a.allapot for a in approvals}
    return {
        "task": _task_sor(t),
        "runs": [
            {
                "id": r.id,
                "trigger": r.trigger,
                "allapot": r.allapot,
                "provider": r.provider,
                "modell": r.modell,
                "kezdes_at": r.kezdes_at.isoformat() if r.kezdes_at else None,
                "veg_at": r.veg_at.isoformat() if r.veg_at else None,
                "hibakod": r.hibakod,
            }
            for r in runs
        ],
        "traces": [
            {
                "id": tr.id,
                "szereplo": tr.szereplo,
                "muvelet": tr.muvelet,
                "eroforras": tr.eroforras,
                "eredmeny": tr.eredmeny,
                "diff": tr.diff,
                "tortent_at": tr.tortent_at.isoformat() if tr.tortent_at else None,
            }
            for tr in traces
        ],
        "proposals": [
            {
                "id": p.id,
                "eszkoz": p.eszkoz,
                "kockazat": p.kockazat,
                "allapot": p.allapot,
                "payload": p.payload,
                "ellenorzesek": p.ellenorzesek,
                "payload_hash": p.payload_hash,
                "jovahagyas_allapot": approval_allapot.get(p.id),
                "letrehozva": p.created_at.isoformat() if p.created_at else None,
            }
            for p in proposals
        ],
    }


class TaskPatchIn(BaseModel):
    #: Optimista zárolás: a kliens által ismert verzió; eltérésnél 409.
    row_version: int
    felelos_id: int | None = None
    prioritas: int | None = None
    allapot: str | None = None
    blokkolo_ok: str | None = None


# A felületről kézzel engedélyezett, MELLÉKHATÁS-MENTES állapotátmenetek.
_KEZI_ALLAPOTOK = {
    TaskState.NEW.value,
    TaskState.NEEDS_INFO.value,
    TaskState.BLOCKED.value,
    TaskState.REJECTED.value,
    TaskState.CANCELLED.value,
}


@router.patch("/tasks/{task_id}")
def task_modositas(
    task_id: int,
    payload: TaskPatchIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    if t.row_version != payload.row_version:
        raise HTTPException(status_code=409, detail="A feladatot időközben módosították - töltsd újra.")
    if payload.felelos_id is not None:
        t.felelos_id = payload.felelos_id or None
    if payload.prioritas is not None:
        t.prioritas = payload.prioritas
    if payload.blokkolo_ok is not None:
        t.blokkolo_ok = payload.blokkolo_ok or None
    if payload.allapot is not None:
        if payload.allapot not in _KEZI_ALLAPOTOK:
            raise HTTPException(status_code=400, detail="Ez az állapot kézzel nem állítható be.")
        t.allapot = payload.allapot
        if payload.allapot in {x.value for x in LEZART_TASK_STATES}:
            t.befejezve_at = _most()
    t.row_version += 1
    db.commit()
    return _task_sor(t)


# ── Jóváhagyások ──────────────────────────────────────────────────────────────


@router.get("/approvals")
def approvals_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Jóváhagyásra váró javaslatok. (A javaslat-generáló és végrehajtó réteg a
    következő fázisokban készül; addig ez a lista üres.)"""
    sorok = db.execute(
        select(Approval, ActionProposal, AdminTask)
        .join(ActionProposal, ActionProposal.id == Approval.proposal_id)
        .join(AdminTask, AdminTask.id == ActionProposal.task_id)
        .where(Approval.allapot == "pending")
        .order_by(Approval.id.desc())
    ).all()
    return {
        "elemek": [
            {
                "approval_id": a.id,
                "proposal_id": p.id,
                "task_id": t.id,
                "tipus": t.tipus,
                "eszkoz": p.eszkoz,
                "kockazat": p.kockazat,
                "cim": t.cim,
                "payload": p.payload,
                "payload_hash": p.payload_hash,
                "partner_nev": t.partner_nev,
                "letrehozva": a.created_at.isoformat() if a.created_at else None,
            }
            for (a, p, t) in sorok
        ]
    }


def _execution_sor(ex: ActionExecution) -> dict:
    return {
        "id": ex.id,
        "proposal_id": ex.proposal_id,
        "approval_id": ex.approval_id,
        "allapot": ex.allapot,
        "probalkozasok": ex.probalkozasok,
        "kulso_azonosito": ex.kulso_azonosito,
        "eredmeny": ex.eredmeny,
        "egyeztetes_allapot": ex.egyeztetes_allapot,
    }


class ApproveIn(BaseModel):
    #: A kliens által látott javaslat-hash — a jóváhagyás EHHEZ kötődik. Ha a
    #: javaslat időközben megváltozott, a kötés nem jön létre (409).
    payload_hash: str
    indok: str | None = None


def _csak_a_felelos_donthet(db: Session, user: Employee) -> None:
    """„Csak a felelősnek" módban (alap) Lara javaslatairól KIZÁRÓLAG Lara
    felelőse (Vidor Gergely) dönthet — a felhasználó kérése: minden hozzá fut be
    jóváhagyásra. Ha a felelős nincs beállítva / nem található, senki nem
    dönthet, amíg a Beállításokban ki nem választják."""
    if not csak_felelosnek(db):
        return
    f = lara_felelos(db)
    if f is None:
        raise HTTPException(
            status_code=403,
            detail="Lara felelőse nincs beállítva — a Beállításokban válaszd ki, ki hagyja jóvá Lara javaslatait.",
        )
    if f.id != user.id:
        raise HTTPException(
            status_code=403,
            detail=f"Lara javaslatairól jelenleg csak a felelőse ({f.full_name}) dönthet.",
        )


@router.post("/approvals/{approval_id}/approve")
def approval_jovahagy(
    approval_id: int,
    payload: ApproveIn,
    db: Session = Depends(get_db),
    # A jóváhagyás a "edit" joghoz kötött; a finomabb pénzügyi/jogi jóváhagyási
    # permissionök (financial_approve/legal_approve) a G fázisban jönnek.
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Egy javaslat jóváhagyása ÉS a guarded végrehajtás megkísérlése. A
    jóváhagyás a beküldött payload-hash-hez kötődik; ha a javaslat időközben
    megváltozott, 409. A tényleges mellékhatás csak akkor fut, ha a policy és a
    globális kapcsolók engedik — egyébként a végrehajtási rekord `blocked`."""
    a = db.get(Approval, approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail="A jóváhagyás nem található.")
    _csak_a_felelos_donthet(db, user)
    if a.allapot != ApprovalState.PENDING.value:
        raise HTTPException(status_code=409, detail=f"A jóváhagyás már nem függőben van ({a.allapot}).")
    proposal = db.get(ActionProposal, a.proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="A javaslat nem található.")
    if payload.payload_hash != proposal.payload_hash:
        raise HTTPException(
            status_code=409,
            detail="A javaslat időközben megváltozott — töltsd újra és nézd át az új javaslatot.",
        )
    # Jóváhagyás rögzítése, majd a guard-láncon át a végrehajtás megkísérlése.
    a.allapot = ApprovalState.APPROVED.value
    a.donto_employee_id = user.id
    a.indok = (payload.indok or "").strip() or None
    a.dontes_at = _most()
    db.flush()
    ex = execute_approved(db, a, approver=user)
    db.commit()
    return {"approval_allapot": a.allapot, "execution": _execution_sor(ex)}


class RejectIn(BaseModel):
    indok: str | None = None


@router.post("/approvals/{approval_id}/reject")
def approval_elutasit(
    approval_id: int,
    payload: RejectIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Javaslat elutasítása. Az elutasítás is tanulási jel (a correction/tanuló
    fázis dolgozza fel)."""
    a = db.get(Approval, approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail="A jóváhagyás nem található.")
    _csak_a_felelos_donthet(db, user)
    if a.allapot != ApprovalState.PENDING.value:
        raise HTTPException(status_code=409, detail=f"A jóváhagyás már nem függőben van ({a.allapot}).")
    a.allapot = ApprovalState.REJECTED.value
    a.donto_employee_id = user.id
    a.indok = (payload.indok or "").strip() or None
    a.dontes_at = _most()
    proposal = db.get(ActionProposal, a.proposal_id)
    if proposal is not None:
        t = db.get(AdminTask, proposal.task_id)
        if t is not None and t.allapot not in {x.value for x in LEZART_TASK_STATES}:
            t.allapot = TaskState.REJECTED.value
            t.befejezve_at = _most()
            t.row_version += 1
    db.commit()
    return {"approval_allapot": a.allapot}


# ── Feladat-műveletek (analyze / corrections / assign / cancel) ───────────────


@router.post("/tasks/{task_id}/analyze")
def task_ujraelemez(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A feladat újraelemzése Larával (L0-biztos: nincs mellékhatás). Jelenleg
    a beérkező-számla forráshoz kötött feladatokra fut."""
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    ref = (t.forras_referenciak or {}).get("bejovo_szamla_id")
    if ref is None:
        raise HTTPException(status_code=400, detail="Ehhez a feladathoz nincs újraelemezhető forrás.")
    bejovo = db.get(BejovoSzamla, int(ref))
    if bejovo is None:
        raise HTTPException(status_code=404, detail="A forrás (beérkező számla) nem található.")
    t = arnyek_elemzes(db, bejovo, trigger="manual_reanalyze")
    db.commit()
    return _task_sor(t)


class ProposeIn(BaseModel):
    eszkoz: str
    payload: dict


@router.post("/tasks/{task_id}/propose")
def task_propose(
    task_id: int,
    body: ProposeIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Javaslat készítése egy feladathoz egy regisztrált eszközre (pl.
    e-mail-válasz). Determinista validálás + integráció-ellenőrzés + policy; a
    valid javaslathoz a policy szerint jóváhagyás is készül. Semmit nem hajt
    végre — a végrehajtás a jóváhagyás után, a guard-láncon megy."""
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    try:
        proposal, dontes = keszit_javaslat(db, t, eszkoz=body.eszkoz, payload=body.payload)
    except JavaslatHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {
        "proposal_id": proposal.id,
        "allapot": proposal.allapot,
        "kockazat": proposal.kockazat,
        "ellenorzesek": proposal.ellenorzesek,
        "decision": dontes.decision.value,
        "reason": dontes.reason,
        "task": _task_sor(t),
    }


@router.post("/tasks/{task_id}/tervezet")
def task_tervezet(
    task_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Lara elkészíti a feladat tervezetét: TIG / szerződés esetén a
    projektkód függő feleinek piszkozatait (előtöltés + modell-kiegészítés a
    megtanult tudásból, összeg csak igazolt forrásból), e-mailnél a levél
    tervezetét (címzett csak igazolt címből). Javaslatként jön létre; végrehajtás
    a jóváhagyás után, a guard-láncon — a kiküldés továbbra is emberi lépés."""
    from app.admin_agent.tervezo import TervezetHiba, email_tervezet, tig_szerzodes_tervezet

    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    try:
        if t.tipus in ("tig", "szerzodes"):
            ter = tig_szerzodes_tervezet(db, t, user)
            extra_hiany: list[str] = []
        elif t.tipus == "email":
            ter = email_tervezet(db, t, user)
            extra_hiany = ter.get("extra_hianyok", [])
        else:
            raise TervezetHiba("Tervezet TIG, szerződés és e-mail feladathoz készíthető.")
        modell = ter.get("modell") or {}
        proposal, dontes = keszit_javaslat(
            db,
            t,
            eszkoz=ter["eszkoz"],
            payload=ter["payload"],
            trigger="tervezet",
            provider="gemini" if modell.get("hasznalt") else "szabaly",
            modell=modell.get("modell"),
            extra_ellenorzesek={"modell": modell, "kapcsolodo_tudas": ter.get("kapcsolodo_tudas")},
            extra_hianyok=extra_hiany,
        )
    except (TervezetHiba, JavaslatHiba) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {
        "proposal_id": proposal.id,
        "allapot": proposal.allapot,
        "decision": dontes.decision.value,
        "reason": dontes.reason,
        "modell": modell.get("allapot"),
        "task": _task_sor(t),
    }


def _lapos(ertek: object, elotag: str = "") -> dict:
    """Beágyazott payload lapítása mezőszintű diffhez (pl. tetelek[0].mezok.netto_osszeg)."""
    ki: dict = {}
    if isinstance(ertek, dict):
        for k, v in ertek.items():
            ki.update(_lapos(v, f"{elotag}.{k}" if elotag else str(k)))
    elif isinstance(ertek, list) and ertek and all(isinstance(x, dict) for x in ertek):
        for i, v in enumerate(ertek):
            ki.update(_lapos(v, f"{elotag}[{i}]"))
    else:
        ki[elotag] = ertek
    return ki


class ProposalEditIn(BaseModel):
    payload: dict
    magyarazat: str | None = None
    #: tenyszeru_hiba (alap) / stilus / egyszeri_kivetel / uj_uzleti_adat / besorolando
    tipus: str | None = None


@router.post("/tasks/{task_id}/proposals/{proposal_id}/edit")
def javaslat_szerkesztes(
    task_id: int,
    proposal_id: int,
    body: ProposalEditIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A javaslat emberi szerkesztése: a különbség JAVÍTÁSKÉNT rögzül (tanulási
    jel), és új javaslat készül ugyanarra az eszközre — a régi leváltódik, a függő
    jóváhagyása lejár. Az új javaslat ugyanazon a validáláson és policy-n megy át."""
    t = db.get(AdminTask, task_id)
    p = db.get(ActionProposal, proposal_id)
    if t is None or p is None or p.task_id != task_id:
        raise HTTPException(status_code=404, detail="A javaslat nem ehhez a feladathoz tartozik.")
    if p.allapot not in ("ready", "draft"):
        raise HTTPException(status_code=409, detail="Ez a javaslat már nem szerkeszthető (leváltva vagy felhasználva).")
    regi = _lapos(p.payload)
    uj = _lapos(body.payload)
    diff = {k: {"elozo": regi.get(k), "uj": uj.get(k)} for k in set(regi) | set(uj) if regi.get(k) != uj.get(k)}
    if not diff:
        raise HTTPException(status_code=400, detail="Nincs változás a javaslatban.")
    tipus = body.tipus if body.tipus in {c.value for c in CorrectionType} else CorrectionType.TENYSZERU_HIBA.value
    db.add(
        Correction(
            task_id=task_id,
            proposal_id=p.id,
            eredeti=dict(p.payload),
            javitott=body.payload,
            mezo_diff=diff,
            javito_employee_id=user.id,
            magyarazat=(body.magyarazat or "").strip() or None,
            tipus=tipus,
            feldolgozas_allapot="uj",
        )
    )
    try:
        uj_p, dontes = keszit_javaslat(db, t, eszkoz=p.eszkoz, payload=body.payload, trigger="emberi_szerkesztes")
    except JavaslatHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"proposal_id": uj_p.id, "allapot": uj_p.allapot, "decision": dontes.decision.value, "valtozott_mezok": sorted(diff)}


@router.get("/tools")
def eszkoz_katalogus(
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A regisztrált eszközök katalógusa (deklarált kockázat, feladattípus,
    mellékhatás). Banki utalást indító/végrehajtó eszköz szándékosan nincs."""
    return {
        "eszkozok": [
            {
                "eszkoz": s.eszkoz,
                "cim": s.cim,
                "kockazat": s.risk.value,
                "tipus": s.tipus,
                "mellekhatas": s.side_effect,
            }
            for s in TOOL_REGISTRY.values()
        ]
    }


class CorrectionIn(BaseModel):
    proposal_id: int | None = None
    #: Mezőszintű javítás - ELHAGYHATÓ: elég egy összefoglaló magyarázat is.
    javitott: dict = Field(default_factory=dict)
    magyarazat: str | None = Field(default=None, max_length=4000)
    #: besorolando / egyszeri_kivetel / stilus / tenyszeru_hiba / uj_uzleti_adat / magyarazat
    tipus: str | None = None


@router.post("/tasks/{task_id}/corrections")
def task_correction(
    task_id: int,
    payload: CorrectionIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Emberi javítás rögzítése (tanulási jel). NEM aktivál szabályt.

    Két módon lehet:
    - MEZŐSZINTŰ javítás (`javitott`): `correction` `uj` állapotban, amit a
      háttér-tanuló dolgoz fel jelöltté;
    - csak ÖSSZEFOGLALÓ MAGYARÁZAT (mit hova kellett volna tenni és miért,
      mezők nélkül): ez emberi kifejezett tanítás, ezért azonnal Lara
      tudásába kerül (jóváhagyott tudás-darab a feladat típusához és
      partneréhez) - ugyanúgy, mint a Kérdésekre adott magyarázat."""
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    magyarazat = (payload.magyarazat or "").strip() or None
    if not payload.javitott and not magyarazat:
        raise HTTPException(
            status_code=400,
            detail="Írd le röviden, mit hova kellett volna tennie és miért — vagy adj meg egy javított mezőt.",
        )
    eredeti = None
    if payload.proposal_id is not None:
        p = db.get(ActionProposal, payload.proposal_id)
        if p is None or p.task_id != task_id:
            raise HTTPException(status_code=404, detail="A javaslat nem ehhez a feladathoz tartozik.")
        eredeti = dict(p.payload)
    csak_magyarazat = not payload.javitott
    if csak_magyarazat:
        tipus = CorrectionType.MAGYARAZAT.value
    else:
        tipus = payload.tipus if payload.tipus in {c.value for c in CorrectionType} else CorrectionType.BESOROLANDO.value
    mezo_diff = _mezo_diff(eredeti or {}, payload.javitott) if payload.javitott else {}
    c = Correction(
        task_id=task_id,
        proposal_id=payload.proposal_id,
        eredeti=eredeti,
        javitott=payload.javitott or None,
        mezo_diff=mezo_diff,
        javito_employee_id=user.id,
        magyarazat=magyarazat,
        tipus=tipus,
        # A csak-magyarázat itt azonnal tudássá válik - a háttér-tanulónak
        # nincs vele dolga.
        feldolgozas_allapot="feldolgozva" if csak_magyarazat else "uj",
    )
    db.add(c)
    db.flush()
    pelda_id = None
    if csak_magyarazat:
        m = MemoryChunk(
            hatokor=t.tipus,
            tartalom=_magyarazat_tudas(t, eredeti, magyarazat or ""),
            forras=f"correction:{c.id}",
            minosites="jovahagyott",
            tanulasi_halmaz="jovahagyott",
            ervenyes=True,  # ember magyarázta — kifejezett tanítás
            regi_korszak=False,
        )
        db.add(m)
        db.flush()
        pelda_id = m.id
    db.commit()
    return {"correction_id": c.id, "tipus": c.tipus, "mezo_diff": mezo_diff, "pelda_id": pelda_id}


def _magyarazat_tudas(t: AdminTask, eredeti: dict | None, magyarazat: str) -> str:
    """A feladathoz adott összefoglaló magyarázat tudás-darabként: a partner
    neve elöl (a partner szerinti visszakeresés ebből talál), mit javasolt
    Lara, és mit mondott az ember."""
    fej = f"„{t.partner_nev}” — " if t.partner_nev else ""
    sor = f"{fej}{t.cim}"
    javaslat = _javaslat_kivonat(eredeti)
    if javaslat:
        sor += f". Lara javaslata ez volt: {javaslat}"
    return f"{sor}. Ember magyarázata (mit hova kellett volna tenni és miért): {magyarazat}"


def _javaslat_kivonat(payload: dict | None, max_hossz: int = 400) -> str:
    """A javaslat payloadjának rövid, olvasható kivonata (csak az egyszerű mezők)."""
    if not payload:
        return ""
    reszek = [
        f"{k}: {v}"
        for k, v in payload.items()
        if isinstance(v, (str, int, float, bool)) and v not in ("", None) and not k.startswith("_")
    ]
    szoveg = "; ".join(reszek)
    return szoveg[:max_hossz] + ("…" if len(szoveg) > max_hossz else "")


def _mezo_diff(eredeti: dict, javitott: dict) -> dict:
    """Mezőszintű különbség (csak a ténylegesen eltérő kulcsok)."""
    diff: dict = {}
    for kulcs in set(eredeti) | set(javitott):
        regi = eredeti.get(kulcs)
        uj = javitott.get(kulcs)
        if regi != uj:
            diff[kulcs] = {"elozo": regi, "uj": uj}
    return diff


class AssignIn(BaseModel):
    felelos_id: int | None = None


@router.post("/tasks/{task_id}/assign")
def task_felelos(
    task_id: int,
    payload: AssignIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    if payload.felelos_id is not None and db.get(Employee, payload.felelos_id) is None:
        raise HTTPException(status_code=400, detail="A kiválasztott felelős nem található.")
    t.felelos_id = payload.felelos_id
    t.row_version += 1
    db.commit()
    return _task_sor(t)


@router.post("/tasks/{task_id}/cancel")
def task_megszakit(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    if t.allapot in {x.value for x in LEZART_TASK_STATES}:
        raise HTTPException(status_code=409, detail="A feladat már lezárt.")
    t.allapot = TaskState.CANCELLED.value
    t.befejezve_at = _most()
    t.row_version += 1
    db.commit()
    return _task_sor(t)


@router.get("/executions/{execution_id}")
def execution_reszlet(
    execution_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    ex = db.get(ActionExecution, execution_id)
    if ex is None:
        raise HTTPException(status_code=404, detail="A végrehajtás nem található.")
    return _execution_sor(ex)


# ── Tudástár (szabályok) ─────────────────────────────────────────────────────


def _rule_sor(r: PlaybookRule) -> dict:
    return {
        "id": r.id,
        "hatokor": r.hatokor,
        "cim": r.cim,
        "feltetelek": r.feltetelek,
        "tartalom": r.tartalom,
        "prioritas": r.prioritas,
        "verzio": r.verzio,
        "allapot": r.allapot,
        "forras_esetek": r.forras_esetek,
        "letrehozva": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/rules")
def rules_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
    hatokor: str | None = Query(default=None),
    allapot: str | None = Query(default=None),
):
    felt = []
    if hatokor:
        felt.append(PlaybookRule.hatokor == hatokor)
    if allapot:
        felt.append(PlaybookRule.allapot == allapot)
    sorok = db.scalars(select(PlaybookRule).where(*felt).order_by(PlaybookRule.id.desc())).all()
    return {"elemek": [_rule_sor(r) for r in sorok]}


class RuleCreateIn(BaseModel):
    hatokor: str
    cim: str = Field(min_length=3, max_length=200)
    tartalom: str = Field(min_length=3, max_length=4000)
    feltetelek: dict | None = None
    prioritas: int = 0
    #: Opcionális: a szabály CSAK ennél a partnernél érvényes (normalizált névvel).
    partner: str | None = None
    #: Opcionális (számlánál): a partner számláinak céltípusa — ezzel a szabály
    #: gépileg is alkalmazható (modell nélkül is kitölti az üres célt).
    cel_tipus: str | None = None
    #: Opcionális: projektkód (pl. HYPE26-0012) — csak létező kód fogadható el.
    projektkod: str | None = None


@router.post("/rules")
def rule_letrehozas(
    payload: RuleCreateIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Kézi szabály felvétele DRAFT állapotban (a Tudástárból: a fejekben lévő
    szokások). Aktívvá csak értékelés után, külön élesítéssel válik (a gépi
    jelölt sem aktiválhatja magát). Partnerhez kötve csak annál a partnernél
    jön elő; céltípussal számlánál gépileg is alkalmazható."""
    from app.admin_agent.memory import partner_kulcs
    from app.models.bejovo_szamla import CEL_TIPUSOK
    from app.models.project_code import ProjectCode

    hatokor = payload.hatokor.strip()
    if hatokor not in _TIPUS_ERTEKEK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen feladattípus: {hatokor}")
    feltetelek = dict(payload.feltetelek or {})
    prioritas = payload.prioritas
    if payload.partner and payload.partner.strip():
        kulcs = partner_kulcs(payload.partner)
        if len(kulcs) < 3:
            raise HTTPException(status_code=400, detail="A partner neve túl rövid az azonosításhoz.")
        feltetelek.update({"partner": kulcs, "partner_nev": payload.partner.strip(), "forras": "kezi"})
        prioritas = max(prioritas, 10)  # partnerre szabott: az általános előtt
    if payload.cel_tipus:
        if hatokor != "szamla" or payload.cel_tipus not in CEL_TIPUSOK:
            raise HTTPException(status_code=400, detail="Céltípus csak számla-szabálynál, a megengedett értékekből adható meg.")
        if not feltetelek.get("partner"):
            raise HTTPException(status_code=400, detail="Céltípushoz partner is kell (különben minden számlára vonatkozna).")
        feltetelek["cel_tipus"] = payload.cel_tipus
    if payload.projektkod and payload.projektkod.strip():
        pc = db.scalar(select(ProjectCode).where(ProjectCode.projektkod.ilike(payload.projektkod.strip())))
        if pc is None:
            raise HTTPException(status_code=400, detail=f"Nincs ilyen projektkód: {payload.projektkod.strip()}")
        feltetelek["projektkod_idk"] = [pc.id]
    r = PlaybookRule(
        hatokor=hatokor,
        cim=payload.cim.strip(),
        tartalom=payload.tartalom.strip(),
        feltetelek=feltetelek or None,
        prioritas=prioritas,
        verzio=1,
        allapot=RuleState.DRAFT.value,
    )
    db.add(r)
    db.commit()
    return _rule_sor(r)


class RulePatchIn(BaseModel):
    cim: str | None = None
    tartalom: str | None = None
    prioritas: int | None = None
    #: Állapotátmenet: draft/pending/active/retired.
    allapot: str | None = None


@router.patch("/rules/{rule_id}")
def rule_modositas(
    rule_id: int,
    payload: RulePatchIn,
    db: Session = Depends(get_db),
    # Az AKTIVÁLÁS a legerősebb (delete = szabályaktiválás) joghoz kötött; a
    # tartalmi szerkesztés "edit" alatt is mehet. A finomabb rule_activate
    # permission a G fázis.
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    r = db.get(PlaybookRule, rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="A szabály nem található.")
    if payload.cim is not None:
        r.cim = payload.cim.strip()
    if payload.tartalom is not None:
        r.tartalom = payload.tartalom
    if payload.prioritas is not None:
        r.prioritas = payload.prioritas
    if payload.allapot is not None:
        if payload.allapot not in {s.value for s in RuleState}:
            raise HTTPException(status_code=400, detail="Ismeretlen szabályállapot.")
        if payload.allapot == RuleState.ACTIVE.value:
            # Aktiválás: külön (erős) jog + legyen sikeres eval. A modell/jelölt
            # nem aktiválhatja magát — csak jogosult ember, API-n át.
            check_page_action(db, user, PAGE, "delete")
            utolso = db.scalar(select(EvalRun).order_by(EvalRun.id.desc()))
            if utolso is None or not utolso.atment:
                raise HTTPException(
                    status_code=409,
                    detail="Aktiválás előtt sikeres értékelés (eval) szükséges — futtass evaluációt.",
                )
        r.allapot = payload.allapot
    db.commit()
    return _rule_sor(r)


@router.post("/rules/{rule_id}/evaluate")
def rule_probal(
    rule_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """„Próba korábbi eseteken": a szabály forrásesetei + a hatókörébe eső
    korrekciók száma (mennyi javítást fedne le)."""
    r = db.get(PlaybookRule, rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="A szabály nem található.")
    illeszkedo = db.scalar(
        select(func.count(Correction.id))
        .join(AdminTask, AdminTask.id == Correction.task_id)
        .where(AdminTask.tipus == r.hatokor)
    ) or 0
    return {"rule_id": r.id, "forras_esetek": r.forras_esetek, "hatokorbe_eso_korrekciok": illeszkedo}


# ── Tanulás és minőség (learning-runs, evaluations, releases) ─────────────────


@router.get("/learning-runs")
def learning_runs_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    # Az önellenőrző és a levelezés-olvasó futásoknak saját listájuk van
    # (GET /self-check/runs, GET /mail-learning).
    sorok = db.scalars(
        select(LearningRun)
        .where(
            ~LearningRun.trigger.like("onellenorzes%"),
            ~LearningRun.trigger.like("levelezes%"),
            ~LearningRun.trigger.like("asszisztens%"),
            ~LearningRun.trigger.like("megerosites%"),
            ~LearningRun.trigger.like("rendszer%"),
        )
        .order_by(LearningRun.id.desc())
        .limit(50)
    ).all()
    return {
        "elemek": [
            {
                "id": lr.id,
                "trigger": lr.trigger,
                "allapot": lr.allapot,
                "feldolgozott_korrekciok": lr.feldolgozott_korrekciok,
                "uj_szabaly_jeloltek": lr.uj_szabaly_jeloltek,
                "uj_pelda_jeloltek": lr.uj_pelda_jeloltek,
                "sop_keresek": lr.sop_keresek,
                "veg_at": lr.veg_at.isoformat() if lr.veg_at else None,
            }
            for lr in sorok
        ]
    }


@router.post("/learning-runs")
def learning_run_inditas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A háttér-tanuló (distill) kézi indítása. Idempotens: csak az új
    korrekciókat dolgozza fel. Nem aktivál szabályt, csak jelölteket készít."""
    lr = distill(db, trigger="manual")
    db.commit()
    return {
        "id": lr.id,
        "feldolgozott_korrekciok": lr.feldolgozott_korrekciok,
        "uj_szabaly_jeloltek": lr.uj_szabaly_jeloltek,
        "uj_pelda_jeloltek": lr.uj_pelda_jeloltek,
        "sop_keresek": lr.sop_keresek,
    }


@router.get("/evaluations")
def evaluations_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    sorok = db.scalars(select(EvalRun).order_by(EvalRun.id.desc()).limit(50)).all()
    return {
        "elemek": [
            {
                "id": e.id,
                "allapot": e.allapot,
                "osszes": e.osszes,
                "sikeres": e.sikeres,
                "kritikus_hiba": e.kritikus_hiba,
                "atment": e.atment,
                "arany": (e.eredmeny or {}).get("arany"),
                "veg_at": e.veg_at.isoformat() if e.veg_at else None,
            }
            for e in sorok
        ]
    }


@router.post("/evaluations")
def evaluation_inditas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Értékelő futtatás. Először beveti a beépített biztonsági eseteket (ha még
    nincsenek), majd végigfut minden érvényes eseten. Sikertelen futás nem
    aktiválhat kiadást."""
    safety_esetek_magveto(db)
    run = run_eval(db)
    db.commit()
    return {
        "id": run.id,
        "osszes": run.osszes,
        "sikeres": run.sikeres,
        "kritikus_hiba": run.kritikus_hiba,
        "atment": run.atment,
        "eredmeny": run.eredmeny,
    }


class ReleaseCreateIn(BaseModel):
    verzio: str
    tipus: str = "rules"
    leiras: str | None = None
    config: dict | None = None


@router.get("/releases")
def releases_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    sorok = db.scalars(select(AgentRelease).order_by(AgentRelease.id.desc()).limit(50)).all()
    return {
        "elemek": [
            {"id": r.id, "verzio": r.verzio, "tipus": r.tipus, "allapot": r.allapot, "leiras": r.leiras}
            for r in sorok
        ]
    }


@router.post("/releases")
def release_letrehozas(
    payload: ReleaseCreateIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    r = AgentRelease(
        verzio=payload.verzio.strip(),
        tipus=payload.tipus,
        leiras=payload.leiras,
        config=payload.config,
        allapot="jelolt",
    )
    db.add(r)
    db.commit()
    return {"id": r.id, "verzio": r.verzio, "allapot": r.allapot}


@router.post("/releases/{release_id}/activate")
def release_aktivalas(
    release_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Kiadás aktiválása. Csak sikeres (atment) értékelés után; a jelölt nem
    aktiválhatja magát. Az előző aktív kiadás visszavontra kerül."""
    r = db.get(AgentRelease, release_id)
    if r is None:
        raise HTTPException(status_code=404, detail="A kiadás nem található.")
    utolso = db.scalar(select(EvalRun).order_by(EvalRun.id.desc()))
    if utolso is None or not utolso.atment:
        raise HTTPException(status_code=409, detail="Aktiválás előtt sikeres értékelés (eval) szükséges.")
    for elozo in db.scalars(select(AgentRelease).where(AgentRelease.allapot == "aktiv")).all():
        elozo.allapot = "visszavont"
    r.allapot = "aktiv"
    r.eval_run_id = utolso.id
    r.aktivalta_employee_id = user.id
    r.aktivalva_at = _most()
    db.commit()
    return {"id": r.id, "allapot": r.allapot, "eval_run_id": r.eval_run_id}


# ── Megfigyelés (projektkód / utókövetés) + tudás-példák (memória) ────────────


@router.post("/observations")
def megfigyeles_inditas(
    visszatekintes_nap: int | None = Query(default=None, ge=1, le=365),
    #: Visszatekintés pontosan a tanulás kezdetétől (Beállítások; alap: 2026-09-01).
    kezdettol: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A megfigyelő kézi futtatása: a projektkódokon / az utókövetésben nemrég
    változott szerződéseket, TIG-eket és kiadásokat rögzíti megfigyelésként, a
    lezárt emberi munkából példa-JELÖLTET készít. Csak olvas + Lara saját
    tábláiba ír; üzleti rekord nem változik. A kézi indítás jogosult felhasználó
    kifejezett döntése, ezért a forrás-kapcsolótól függetlenül fut (az ütemezett
    futás viszont csak bekapcsolt forrással)."""
    eredmeny = megfigyeles(db, visszatekintes_nap=visszatekintes_nap, kenyszeritett=True, kezdettol=kezdettol)
    db.commit()
    return eredmeny


# ── Lara önellenőrzése és kérdései ─────────────────────────────────────────────


def _kerdes_sor(k: LaraKerdes) -> dict:
    return {
        "id": k.id,
        "tipus": k.tipus,
        "allapot": k.allapot,
        "partner_nev": k.partner_nev,
        "kerdes": k.kerdes,
        "kontextus": k.kontextus,
        "valasz_tipus": k.valasz_tipus,
        "valasz_szoveg": k.valasz_szoveg,
        "megvalaszolva_at": k.megvalaszolva_at.isoformat() if k.megvalaszolva_at else None,
        "szabaly_id": k.szabaly_id,
        "letrehozva": k.created_at.isoformat() if k.created_at else None,
    }


@router.post("/self-check")
def onellenorzes_inditas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Lara önellenőrzése most: előbb a friss rögzítések visszajátszása, majd a
    jelenlegi tudással „vak" jóslat minden rögzített számlára és lezárt eseti
    szerződés/TIG döntésre (Utókövetés), összevetés a valósággal; ahol nem érti
    az eltérést, kérdez. Üzleti rekord nem változik."""
    from app.admin_agent.onellenorzes import onellenorzes
    from app.admin_agent.visszajatszas import visszajatszas

    from app.admin_agent.megerosites import futtat

    vj = visszajatszas(db)
    eredmeny = onellenorzes(db, trigger="onellenorzes:kezi")
    db.commit()
    m = futtat(db, trigger="megerosites:onellenorzes")
    db.commit()
    return {
        **eredmeny,
        "visszajatszas": {k: vj[k] for k in ("uj_szamla", "uj_pelda", "uj_szabaly_jelolt")},
        "megerosites": {k: m[k] for k in ("auto_jovahagyott", "uj_szabalyjavaslat")},
    }


# ── Gyorsított tanulás: megerősítés, jelentés szerinti keresés, összesítő ────


def _gyorsitas_beallitasok(db: Session) -> dict:
    lim = get_settings(db).limitek or {}
    from app.admin_agent.megerosites import beallitas

    auto, min_eset = beallitas(db)
    return {
        "auto_jovahagyas": auto,
        "auto_jovahagyas_min": min_eset,
        "szemantikus_kereses": lim.get("szemantikus_kereses") is not False,
        "napi_osszesito": lim.get("napi_osszesito") is not False,
        "kerdes_ertesites": lim.get("kerdes_ertesites") is not False,
    }


def _rangsor_sor(pont: float, m: MemoryChunk, okok: list[str]) -> dict:
    return {**_memory_sor(m), "ertek": pont, "ertek_okok": okok}


@router.get("/learning-boost")
def gyorsitas_allapot(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A gyorsított tanulás állapota: automatikus jóváhagyások, szabályjavaslatok,
    a jelentés szerinti keresés lefedettsége és a legértékesebb várakozó jelöltek."""
    from app.admin_agent.embedding import lefedettseg
    from app.admin_agent.megerosites import allapot
    from app.admin_agent.osszesito import ertek_rangsor

    rangsor = ertek_rangsor(db)
    return {
        "beallitasok": _gyorsitas_beallitasok(db),
        "megerosites": allapot(db),
        "beagyazas": lefedettseg(db),
        "varakozo": len(rangsor),
        "legertekesebb": [_rangsor_sor(p, m, o) for p, m, o in rangsor[:8]],
    }


@router.post("/learning-boost/confirm")
def gyorsitas_megerosites(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Megerősítés MOST: a valóság által igazolt példák automatikus jóváhagyása
    és szabályjavaslat a jóváhagyott csoportokból (szabály sosem élesedik magától)."""
    from app.admin_agent.megerosites import futtat

    eredmeny = futtat(db, trigger="megerosites:kezi")
    db.commit()
    return eredmeny


@router.post("/learning-boost/embed")
def gyorsitas_beagyazas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A még vektor nélküli tudás-darabok beágyazása MOST (~40 mp egy kérésben;
    a többit a félóránkénti futás folytatja)."""
    from app.admin_agent.embedding import bekapcsolva, elerheto, feltolt, lefedettseg

    if not elerheto():
        raise HTTPException(status_code=400, detail="Beállítás szükséges: nincs Gemini-kulcs a beágyazáshoz.")
    if not bekapcsolva(db):
        raise HTTPException(status_code=400, detail="A jelentés szerinti keresés ki van kapcsolva (Beállítások).")
    eredmeny = feltolt(db, max_db=400, max_mp=40)
    db.commit()
    return {**eredmeny, "lefedettseg": lefedettseg(db)}


@router.get("/mail-learning")
def levelezes_allapot(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A szamla@ levelezésből tanulás állapota: kapcsoló, Gmail-hitelesítés,
    feldolgozott szálak, jelöltek, futások."""
    from app.admin_agent.levelezes import allapot

    return allapot(db)


@router.post("/mail-learning/run")
def levelezes_futtatas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A levelezés feldolgozása MOST (legfeljebb 100 szál és ~40 mp egy
    kérésben, hogy ne fusson időtúllépésbe; a többit a következő futás - kézi
    vagy félóránkénti - folytatja). Csak olvas; a
    szálakból tudás-jelölt lesz, ami jóváhagyás után kerül Lara tudásába."""
    import logging

    from app.admin_agent.levelezes import MAX_MP_KEZI, levelezes_tanulas

    try:
        eredmeny = levelezes_tanulas(db, trigger="levelezes:kezi", max_szal=100, max_mp=MAX_MP_KEZI)
    except Exception as exc:  # noqa: BLE001 - érthető hiba a felületnek a néma 500 helyett
        db.rollback()
        logging.getLogger(__name__).exception("Levelezés kézi feldolgozása sikertelen.")
        raise HTTPException(
            status_code=500,
            detail=f"A levelezés feldolgozása hibára futott ({type(exc).__name__}: {str(exc)[:200]}).",
        ) from exc
    if eredmeny.get("allapot") == "kikapcsolva":
        raise HTTPException(status_code=400, detail="A levelezés olvasása ki van kapcsolva (Beállítások).")
    db.commit()
    return eredmeny


@router.get("/assistant-learning")
def asszisztens_allapot(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Mit figyelt meg Lara az AI asszisztens munkájából: kérések, végrehajtott /
    elutasított műveletek, témák, jelöltek, futások."""
    from app.admin_agent.asszisztens import allapot

    return allapot(db)


@router.post("/assistant-learning/run")
def asszisztens_futtatas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Az AI asszisztens lezárt kérés-köreinek feldolgozása MOST (csak olvas;
    körönként tudás-jelölt, jóváhagyás után kerül Lara tudásába)."""
    from app.admin_agent.asszisztens import asszisztens_tanulas

    eredmeny = asszisztens_tanulas(db, trigger="asszisztens:kezi")
    if eredmeny.get("allapot") == "kikapcsolva":
        raise HTTPException(status_code=400, detail="Az AI asszisztens figyelése ki van kapcsolva (Beállítások).")
    db.commit()
    return eredmeny


@router.get("/system-learning")
def rendszer_allapot(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A teljes rendszer figyelésének állapota: figyelt modulok, projektkód-
    életutak, a legaktívabb területek, futások."""
    from app.admin_agent.rendszer import allapot

    return allapot(db)


@router.post("/system-learning/run")
def rendszer_futtatas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A rendszer átnézése MOST (csak olvas; tudás a Tudástárba)."""
    from app.admin_agent.rendszer import rendszer_figyeles

    eredmeny = rendszer_figyeles(db, trigger="rendszer:kezi")
    if eredmeny.get("allapot") == "kikapcsolva":
        raise HTTPException(status_code=400, detail="A teljes rendszer figyelése ki van kapcsolva (Beállítások).")
    db.commit()
    return eredmeny


@router.get("/self-check/runs")
def onellenorzes_futasok(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Az önellenőrző futások (legújabb elöl): ebből látszik, hogyan nő Lara
    találati aránya a tudásával."""
    from app.admin_agent.onellenorzes import futasok

    return {"elemek": futasok(db)}


@router.get("/questions")
def kerdesek_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
    allapot: str = Query(default="nyitott"),
    limit: int = Query(default=100, ge=1, le=500),
):
    felt = [] if allapot == "mind" else [LaraKerdes.allapot == allapot]
    sorok = db.scalars(select(LaraKerdes).where(*felt).order_by(LaraKerdes.id.desc()).limit(limit)).all()
    return {"elemek": [_kerdes_sor(k) for k in sorok]}


class ValaszIn(BaseModel):
    #: mindig | kivetel | magyarazat | hibas | elvet
    valasz_tipus: str
    magyarazat: str | None = Field(default=None, max_length=2000)
    #: „mindig így" esetén: élesítse-e azonnal a szabályt (joggal + sikeres eval mellett).
    elesit: bool = True


@router.post("/questions/{kerdes_id}/answer")
def kerdes_valasz(
    kerdes_id: int,
    body: ValaszIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Válasz Lara kérdésére — a válasz tudássá válik (szabály / magyarázat /
    kivétel), a „hibás rögzítés" nem tanít. A „mindig így" szabály csak akkor
    élesedik azonnal, ha a válaszolónak van élesítési joga és az utolsó értékelés
    átment; különben jelöltként a Tudástárba kerül."""
    from app.admin_agent.onellenorzes import ValaszHiba, valaszol

    k = db.get(LaraKerdes, kerdes_id)
    if k is None:
        raise HTTPException(status_code=404, detail="A kérdés nem található.")
    elesithet = False
    if body.valasz_tipus == "mindig" and body.elesit:
        try:
            check_page_action(db, user, PAGE, "delete")
            utolso = db.scalar(select(EvalRun).order_by(EvalRun.id.desc()))
            elesithet = bool(utolso is not None and utolso.atment)
        except HTTPException:
            elesithet = False
    try:
        eredmeny = valaszol(db, k, valasz_tipus=body.valasz_tipus, magyarazat=body.magyarazat,
                            user_id=user.id, elesithet=elesithet)
    except ValaszHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"kerdes": _kerdes_sor(k), **eredmeny}


@router.get("/knowledge-graph")
def tudashalo_lekeres(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """A Tudásháló: a megtanult tudás kapcsolati gráfja (pontok, kapcsolatok
    bizonyossággal és első megjelenéssel). Csak olvas."""
    from app.admin_agent.tudashalo import tudashalo

    return tudashalo(db)


@router.post("/replays")
def visszajatszas_inditas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Visszajátszás: a tanulás kezdete óta rögzített számláknál összeveti az
    érkeztető eredeti javaslatát a végső emberi döntéssel. Példa-JELÖLTEK és
    partnerenkénti szabály-JELÖLTEK születnek (emberi jóváhagyásig nem élesek),
    és kiszámolja a találati arányt. Üzleti rekord nem változik."""
    from app.admin_agent.visszajatszas import visszajatszas

    eredmeny = visszajatszas(db)
    db.commit()
    return eredmeny


@router.get("/replays/summary")
def visszajatszas_osszesites(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Találati arány: az érkeztető (és ahol volt, Lara) javaslata hányszor
    egyezett a végső emberi döntéssel — összesen és hetente."""
    from app.admin_agent.visszajatszas import osszesites

    return osszesites(db)


def _memory_sor(m: MemoryChunk) -> dict:
    return {
        "id": m.id,
        "hatokor": m.hatokor,
        "tartalom": m.tartalom,
        "forras": m.forras,
        "minosites": m.minosites,
        "ervenyes": m.ervenyes,
        "visszavont": m.visszavont,
        "regi_korszak": m.regi_korszak,
        "forras_keletkezes": m.forras_keletkezes.isoformat() if m.forras_keletkezes else None,
        "letrehozva": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/memory")
def memory_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
    hatokor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    #: A régi korszakból félretett jelölteket is kéri (alapból nem).
    felretett: bool = Query(default=False),
    #: "ertek": a várakozó jelöltek érték szerint elöl (lásd admin_agent/osszesito.py).
    rendezes: str | None = Query(default=None),
):
    """A tudás-példák (jelöltek + jóváhagyottak). A holdout sosem jelenik meg itt.
    A régi korszak (a tanulás kezdete előtti / Notionből importált) félretett
    jelöltjei alapból nem jönnek — csak a számuk."""
    felt = [MemoryChunk.tanulasi_halmaz == "jovahagyott"]
    if hatokor:
        felt.append(MemoryChunk.hatokor == hatokor)
    if not felretett:
        felt.append(MemoryChunk.minosites != FELRETEVE)
    sorok = db.scalars(select(MemoryChunk).where(*felt).order_by(MemoryChunk.id.desc()).limit(limit)).all()
    felretett_db = db.scalar(
        select(func.count(MemoryChunk.id)).where(
            MemoryChunk.minosites == FELRETEVE, MemoryChunk.ervenyes.is_(False), MemoryChunk.visszavont.is_(False)
        )
    ) or 0
    elemek = [_memory_sor(m) for m in sorok]
    if rendezes == "ertek":
        from app.admin_agent.osszesito import ertek_rangsor

        rang = {m.id: (p, o) for p, m, o in ertek_rangsor(db)}
        for e in elemek:
            if e["id"] in rang:
                e["ertek"], e["ertek_okok"] = rang[e["id"]]
        elemek.sort(key=lambda e: (e.get("ertek") is None, -(e.get("ertek") or 0), -e["id"]))
    return {
        "elemek": elemek,
        "felretett_regi": felretett_db,
        "tanulas_kezdete": tanulas_kezdete_datum(db).isoformat(),
    }


class MemoryPatchIn(BaseModel):
    #: True = jóváhagyás (éles döntésben használható), False = vissza jelöltre.
    ervenyes: bool | None = None
    #: True = elvetés/visszavonás (többé nem használható).
    visszavont: bool | None = None


class MemoryBulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    #: "jovahagy" vagy "elvet"
    muvelet: str


@router.post("/memory/bulk")
def memory_tomeges(
    body: MemoryBulkIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """KIJELÖLT példák jóváhagyása / elvetése (a felhasználó egyenként pipálja
    ki őket — nincs „mindent jóváhagy”). A jóváhagyás tudás-aktiválási joghoz
    (delete) kötött; elvetett példa nem hagyható jóvá."""
    if body.muvelet not in ("jovahagy", "elvet"):
        raise HTTPException(status_code=400, detail="Ismeretlen művelet.")
    if body.muvelet == "jovahagy":
        check_page_action(db, user, PAGE, "delete")
    sorok = db.scalars(select(MemoryChunk).where(MemoryChunk.id.in_(body.ids))).all()
    kesz = 0
    kihagyott = 0
    for m in sorok:
        if body.muvelet == "jovahagy":
            if m.visszavont:
                kihagyott += 1
                continue
            m.ervenyes = True
            m.minosites = "jovahagyott"
        else:
            m.visszavont = True
            m.ervenyes = False
            m.minosites = "elvetett"
        kesz += 1
    db.commit()
    return {"modositva": kesz, "kihagyva": kihagyott}


@router.patch("/memory/{memory_id}")
def memory_modositas(
    memory_id: int,
    payload: MemoryPatchIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Példa jóváhagyása / elvetése. A JÓVÁHAGYÁS (éles döntésbe engedés) a
    tudás-aktiválási joghoz (delete) kötött — egy példa nem kerülhet észrevétlenül
    az éles döntési környezetbe."""
    m = db.get(MemoryChunk, memory_id)
    if m is None:
        raise HTTPException(status_code=404, detail="A példa nem található.")
    if payload.ervenyes is True:
        check_page_action(db, user, PAGE, "delete")
        if m.visszavont:
            raise HTTPException(status_code=409, detail="Elvetett példa nem hagyható jóvá.")
        m.ervenyes = True
        m.minosites = "jovahagyott"
    elif payload.ervenyes is False:
        m.ervenyes = False
        # Ha Lara hagyta jóvá magától, és ember vette vissza, a megerősítés
        # többé nem hagyhatja jóvá újra (lásd admin_agent/megerosites.py).
        m.minosites = "kezi_jelolt" if m.minosites == "auto_jovahagyott" else "jelolt"
    if payload.visszavont is True:
        m.visszavont = True
        m.ervenyes = False
        m.minosites = "elvetett"
    db.commit()
    return _memory_sor(m)


# ── Bizalmi szintek (trust policies) ──────────────────────────────────────────


@router.get("/trust-policies")
def trust_policies_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    sorok = db.scalars(select(TrustPolicy).order_by(TrustPolicy.tipus, TrustPolicy.altipus)).all()
    return {
        "elemek": [
            {
                "id": p.id,
                "tipus": p.tipus,
                "altipus": p.altipus,
                "szint": p.szint,
                "auto_engedett_altipusok": p.auto_engedett_altipusok or [],
            }
            for p in sorok
        ]
    }


class TrustPatchIn(BaseModel):
    szint: str | None = None
    auto_engedett_altipusok: list[str] | None = None


@router.patch("/trust-policies/{policy_id}")
def trust_policy_modositas(
    policy_id: int,
    payload: TrustPatchIn,
    db: Session = Depends(get_db),
    # A bizalmi szint módosítása a legerősebb (delete = trust_change) joghoz
    # kötött. A MODELL a saját trust policyját nem módosíthatja — csak jogosult
    # ember, API-n át. R3-tiltást a magasabb szint sem old fel (policy engine).
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    p = db.get(TrustPolicy, policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="A bizalmi szabály nem található.")
    if payload.szint is not None:
        if payload.szint not in {t.value for t in TrustLevel}:
            raise HTTPException(status_code=400, detail="Ismeretlen bizalmi szint.")
        p.szint = payload.szint
    if payload.auto_engedett_altipusok is not None:
        p.auto_engedett_altipusok = payload.auto_engedett_altipusok
    p.modositotta_employee_id = user.id
    db.commit()
    return {
        "id": p.id,
        "tipus": p.tipus,
        "altipus": p.altipus,
        "szint": p.szint,
        "auto_engedett_altipusok": p.auto_engedett_altipusok or [],
    }


# ── Napló (audit) ─────────────────────────────────────────────────────────────


@router.get("/audit")
def audit_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
    task_id: int | None = Query(default=None),
    eroforras: str | None = Query(default=None),
    eredmeny: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Auditnyomvonal (append-only). Az alkalmazásszerepkör nem törölheti — csak
    olvasható. Szűrés task/erőforrás/eredmény szerint."""
    felt = []
    if task_id is not None:
        felt.append(ActionTrace.task_id == task_id)
    if eroforras:
        felt.append(ActionTrace.eroforras == eroforras)
    if eredmeny:
        felt.append(ActionTrace.eredmeny == eredmeny)
    ossz = db.scalar(select(func.count(ActionTrace.id)).where(*felt)) or 0
    sorok = db.scalars(
        select(ActionTrace).where(*felt).order_by(ActionTrace.id.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "osszesen": ossz,
        "elemek": [
            {
                "id": tr.id,
                "task_id": tr.task_id,
                "szereplo": tr.szereplo,
                "muvelet": tr.muvelet,
                "eroforras": tr.eroforras,
                "eredmeny": tr.eredmeny,
                "tortent_at": tr.tortent_at.isoformat() if tr.tortent_at else None,
            }
            for tr in sorok
        ],
    }


# ── Beállítások + vészleállítás ──────────────────────────────────────────────


@router.get("/settings")
def settings_lekeres(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    s = get_settings(db)
    db.commit()
    return {
        "module_enabled": s.module_enabled,
        "side_effects_enabled": s.side_effects_enabled,
        "kill_switch": s.kill_switch,
        "kill_switch_indok": s.kill_switch_indok,
        "engedett_forrasok": s.engedett_forrasok or {},
        "limitek": s.limitek or {},
        "tanulas_kezdete": tanulas_kezdete_datum(db).isoformat(),
        "integraciok": integracio_allapotok(),
        **_felelos_allapot(db),
    }


def _felelos_allapot(db: Session) -> dict:
    f = lara_felelos(db)
    return {
        "felelos": {"id": f.id, "nev": f.full_name} if f is not None else None,
        "csak_felelosnek": csak_felelosnek(db),
    }


_LEZART_FELADAT = ("completed", "rejected", "cancelled")


def _nyitott_feladatok_a_felelosre(db: Session) -> int:
    """„Csak a felelősnek" módban minden NYITOTT Lara-feladat a felelősé."""
    if not csak_felelosnek(db):
        return 0
    f = lara_felelos(db)
    if f is None:
        return 0
    sorok = db.scalars(
        select(AdminTask).where(
            AdminTask.allapot.not_in(_LEZART_FELADAT),
            AdminTask.felelos_id.is_distinct_from(f.id),
        )
    ).all()
    for t in sorok:
        t.felelos_id = f.id
    return len(sorok)


class SettingsPatchIn(BaseModel):
    module_enabled: bool | None = None
    side_effects_enabled: bool | None = None
    engedett_forrasok: dict | None = None
    limitek: dict | None = None
    #: A tanulás kezdete: ettől a naptól keletkezett rekordokból tanul Lara.
    tanulas_kezdete: date | None = None


@router.patch("/settings")
def settings_modositas(
    payload: SettingsPatchIn,
    db: Session = Depends(get_db),
    # A magas kockázatú kapcsolók (modul/mellékhatás) a legerősebb műveleti
    # joghoz kötöttek; a finomabb (financial/legal/trust) permissionök a G fázis.
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    s = get_settings(db)
    if payload.module_enabled is not None:
        s.module_enabled = payload.module_enabled
    if payload.side_effects_enabled is not None:
        s.side_effects_enabled = payload.side_effects_enabled
    if payload.engedett_forrasok is not None:
        s.engedett_forrasok = payload.engedett_forrasok
    if payload.limitek is not None:
        s.limitek = payload.limitek
    korszak = None
    if payload.tanulas_kezdete is not None:
        if payload.tanulas_kezdete > date.today():
            raise HTTPException(status_code=400, detail="A tanulás kezdete nem lehet a jövőben.")
        s.limitek = {**(s.limitek or {}), "tanulas_kezdete": payload.tanulas_kezdete.isoformat()}
        db.flush()
        # A meglévő példák újrabesorolása az új kezdőnap szerint.
        korszak = korszak_rendezes(db)
    if payload.limitek is not None and isinstance(payload.limitek.get("felelos_employee_id"), int):
        if db.get(Employee, payload.limitek["felelos_employee_id"]) is None:
            raise HTTPException(status_code=400, detail="A kiválasztott felelős nem található.")
    s.modositotta_employee_id = user.id
    db.flush()
    atvezetve = _nyitott_feladatok_a_felelosre(db)
    db.commit()
    return {
        "atvezetett_feladat": atvezetve,
        **_felelos_allapot(db),
        "korszak": korszak,
        "tanulas_kezdete": tanulas_kezdete_datum(db).isoformat(),
        "module_enabled": s.module_enabled,
        "side_effects_enabled": s.side_effects_enabled,
        "kill_switch": s.kill_switch,
        "kill_switch_indok": s.kill_switch_indok,
        "engedett_forrasok": s.engedett_forrasok or {},
        "limitek": s.limitek or {},
        "integraciok": integracio_allapotok(),
    }


class PauseIn(BaseModel):
    indok: str | None = None


@router.post("/pause")
def veszleallitas_be(
    payload: PauseIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Globális vészleállítás BE: Lara TELJESEN leáll minden szálon - az
    ütemezett feladatok (megfigyelés, tanulás, önellenőrzés, levelezés,
    értékelés) nem futnak, a futók a következő ellenőrzési ponton megállnak,
    és az API minden futtató/módosító kérése 423-at ad. A tudás és a
    kapcsolók állása megmarad; a /resume pontosan oda tér vissza. A már
    elindult, nem megszakítható külső műveleteket ez NEM vonja vissza."""
    s = get_settings(db)
    s.kill_switch = True
    s.kill_switch_indok = (payload.indok or "").strip() or None
    s.modositotta_employee_id = user.id
    _kapcsolas_naplo(db, user, "veszleallitas", "leallitva", {"indok": s.kill_switch_indok})
    db.commit()
    return {"kill_switch": True, "indok": s.kill_switch_indok}


def _kapcsolas_naplo(db: Session, user: Employee, muvelet: str, eredmeny: str, diff: dict) -> None:
    """A leállítás / visszakapcsolás nyoma a Naplóban (ki, mikor, miért)."""
    db.add(
        ActionTrace(
            task_id=None,
            szereplo="human",
            szereplo_employee_id=user.id,
            muvelet=muvelet,
            eroforras="lara",
            diff=diff,
            eredmeny=eredmeny,
            tortent_at=_most(),
        )
    )


@router.post("/resume")
def veszleallitas_ki(
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Lara VISSZAKAPCSOLÁSA a vészleállítás után. A tudás és a kapcsolók
    (modul, mellékhatás, források) a leállítás előtti állapotban vannak; az
    ütemezett feladatok a következő időpontjukban újra futnak."""
    s = get_settings(db)
    elozo_indok = s.kill_switch_indok
    s.kill_switch = False
    s.kill_switch_indok = None
    s.modositotta_employee_id = user.id
    _kapcsolas_naplo(db, user, "visszakapcsolas", "visszakapcsolva", {"leallitas_indoka": elozo_indok})
    db.commit()
    return {"kill_switch": False}
