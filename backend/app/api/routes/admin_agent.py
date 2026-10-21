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


def _task_sor(t: AdminTask, user: Employee | None = None) -> dict:
    from app.admin_agent.megoldas import lathato_megoldas

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
        "parent_task_id": t.parent_task_id,
        "blokkolo_ok": t.blokkolo_ok,
        "utolso_hiba": t.utolso_hiba,
        "row_version": t.row_version,
        "letrehozva": t.created_at.isoformat() if t.created_at else None,
        "befejezve_at": t.befejezve_at.isoformat() if t.befejezve_at else None,
        # Lara megoldási javaslata (az alap-lépések mindenkinek, a modell-rész
        # csak annak, akinek a jogosultságával készült — lásd admin_agent/megoldas.py).
        "lara_megoldas": lathato_megoldas(t, user),
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
    #: Diszpó-feladatnál a forgatás (projekt).
    project_id: int | None = None
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
        project_id=payload.project_id,
        partner_nev=(payload.partner_nev or "").strip() or None,
        trust_level="L0",
    )
    db.add(t)
    db.flush()
    if t.tipus == "diszpo" and t.project_id is None:
        from app.admin_agent.diszpo_tervezo import forgatas_kereses

        t.project_id = forgatas_kereses(db, project_code_id=t.project_code_id)
    if t.tipus == "osszefogo":
        from app.admin_agent import osszefogo

        osszefogo.ertelmez(db, t)
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
    user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    return _task_sor(t, user)


@router.post("/tasks/{task_id}/solution")
def task_megoldas(
    task_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Lara megoldási javaslata a feladathoz — bármely feladathoz, a kérdésekből
    született javítási feladatokhoz is. Utánanéz az érintett rekordoknak az AI
    asszisztens CSAK OLVASÓ eszközeivel (a kérő jogosultságával), és konkrét
    lépéseket javasol. Semmit nem módosít."""
    from app.admin_agent.megoldas import ai_megoldas
    from app.admin_agent.nyomozas import elerheto
    from app.admin_agent.settings_service import leallitva

    _csak_a_felelos_donthet(db, user)
    if leallitva(db):
        raise HTTPException(status_code=409, detail="Lara le van állítva (vészleállítás).")
    if not elerheto():
        raise HTTPException(status_code=409, detail="Beállítás szükséges: a szerveren nincs Gemini-kulcs.")
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    ai_megoldas(db, t, user)
    db.commit()
    return _task_sor(t, user)


@router.get("/tasks/{task_id}/timeline")
def task_idovonal(
    task_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
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
        "task": _task_sor(t, user),
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
    """Jóváhagyásra váró javaslatok, mindegyikhez emberi nyelvű leírással arról,
    mi fog történni jóváhagyáskor."""
    from app.admin_agent.javaslat_leiras import leiras as javaslat_leiras

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
                # Emberi nyelven: mi fog történni jóváhagyáskor (lásd admin_agent/javaslat_leiras.py).
                "leiras": javaslat_leiras(db, p, t),
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


class TervezetIn(BaseModel):
    #: Diszpó-feladatnál: mit készítsen Lara.
    brief: bool = True
    technika: bool = True
    diszpo_szoveg: bool = True
    #: Diszpó-feladatnál a forgatás, ha a feladaton még nincs.
    project_id: int | None = None


@router.post("/tasks/{task_id}/tervezet")
def task_tervezet(
    task_id: int,
    body: TervezetIn | None = None,
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
        elif t.tipus == "diszpo":
            ter = _diszpo_ter(db, t, body or TervezetIn())
            extra_hiany = []
        else:
            raise TervezetHiba("Tervezet TIG, szerződés, e-mail és diszpó feladathoz készíthető.")
        modell = ter.get("modell") or {}
        proposal, dontes = keszit_javaslat(
            db,
            t,
            eszkoz=ter["eszkoz"],
            payload=ter["payload"],
            trigger="tervezet",
            provider="gemini" if modell.get("hasznalt") else "szabaly",
            modell=modell.get("modell"),
            extra_ellenorzesek={"modell": modell, "kapcsolodo_tudas": ter.get("kapcsolodo_tudas"),
                                **({"tapasztalat": ter["tapasztalat"]} if ter.get("tapasztalat") else {})},
            extra_hianyok=extra_hiany,
        )
    except (TervezetHiba, JavaslatHiba, DiszpoHiba) as exc:
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


from app.admin_agent.diszpo_tervezo import DiszpoHiba  # noqa: E402


def _diszpo_ter(db: Session, t: AdminTask, body: TervezetIn) -> dict:
    from app.admin_agent.diszpo_tervezo import diszpo_tervezet, forgatas_kereses
    from app.models.project import Project

    if body.project_id:
        t.project_id = forgatas_kereses(db, project_id=body.project_id)
    if t.project_id is None:
        t.project_id = forgatas_kereses(db, project_code_id=t.project_code_id)
    if t.project_id is None:
        raise DiszpoHiba("Nem egyértelmű, melyik forgatásról van szó - add meg a forgatást (projektet).")
    project = db.get(Project, t.project_id)
    if project is None:
        raise DiszpoHiba("A forgatás nem található.")
    if t.project_code_id is None:
        t.project_code_id = project.project_code_id
    return diszpo_tervezet(db, project, brief=body.brief, technika=body.technika, diszpo_szoveg=body.diszpo_szoveg)


@router.get("/diszpo/{project_id}/tapasztalat")
def diszpo_tapasztalat(
    project_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Előnézet: a hasonló korábbi forgatások, a tapasztalat szerinti technikai
    csomag (elérhetőséggel) és a visszatérő brief-instrukciók. Csak olvas."""
    from app.admin_agent.diszpo_tervezo import (
        diszpo_szoveg_javaslat,
        hasonlo_forgatasok,
        technika_javaslat,
        visszatero_instrukciok,
    )
    from app.models.project import Project

    from app.admin_agent.forgatas_ismeret import profil as forgatas_profil
    from app.admin_agent.forgatas_ismeret import tapasztalat_kivonat, tipus_tapasztalat
    from app.admin_agent.diszpo_tervezo import tanulasi_korpusz

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="A forgatás nem található.")
    k = tanulasi_korpusz(db, project)
    felismeres = forgatas_profil(db, project)
    hasonlok = hasonlo_forgatasok(db, project, k=k, felismeres=felismeres)
    tipus_tap = tipus_tapasztalat(k, felismeres)
    return {
        "felismert_feladat": felismeres,
        "feladat_tapasztalat": tapasztalat_kivonat(tipus_tap),
        "hasonlo_forgatasok": [
            {"id": h["project"].id, "nev": h["project"].nev, "datum": h["project"].forgatas_datuma.isoformat(),
             "pont": round(h["pont"], 1), "okok": h["okok"]}
            for h in hasonlok
        ],
        "technika": technika_javaslat(db, project, hasonlok, tipus_tap=tipus_tap),
        "visszatero_instrukciok": visszatero_instrukciok(hasonlok),
        "diszpo_szoveg": diszpo_szoveg_javaslat(project, hasonlok),
    }


class DiszpoFeladatIn(BaseModel):
    brief: bool = True
    technika: bool = True
    diszpo_szoveg: bool = True


class DiszpoGeneralasIn(BaseModel):
    #: Mit írjon meg Lara: a stábnak szóló BRIEF szövegét, vagy a TECHNIKAI
    #: csomagot (eszközlista).
    resz: str


@router.post("/diszpo/{project_id}/generalas")
def diszpo_generalas(
    project_id: int,
    body: DiszpoGeneralasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """EGY GOMBNYOMÁSOS brief / technika (a felhasználó kérése): Lara a
    tanultak alapján (hasonló korábbi forgatások, az ilyen feladatú forgatások
    tapasztalata, a jóváhagyott tudás) megírja a kész brief-szöveget, illetve
    összeállítja a technikai csomagot - ugyanaz a motor, mint a jóváhagyásos
    tervezetnél (lásd admin_agent/diszpo_tervezo.diszpo_tervezet).

    CSAK OLVAS: Lara itt semmit nem ír a projektre és nem foglal eszközt. A
    kész szöveget / listát a gombot nyomó EMBER írja be a saját szerkesztési
    jogával (a felület ezt rögtön megteszi, visszavonhatóan) - így Lara
    biztonsági szabályai (alapból semmit nem hajt végre magától, jóváhagyás
    csak a felelősétől) érintetlenek maradnak. Leállított Laránál (vészleállítás)
    nem fut (lásd _nem_leallitva)."""
    from app.admin_agent.diszpo_tervezo import diszpo_tervezet
    from app.models.project import Project

    if body.resz not in ("brief", "technika"):
        raise HTTPException(status_code=400, detail="Mit írjon meg Lara: „brief” vagy „technika”.")
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="A forgatás nem található.")
    try:
        ter = diszpo_tervezet(
            db, project, brief=body.resz == "brief", technika=body.resz == "technika", diszpo_szoveg=False
        )
    except DiszpoHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    p, m = ter["payload"], ter["modell"]
    figy = [f for f in (m.get("figyelmeztetesek") or []) if "jóváhagyás esetén" not in f]
    db.commit()
    return {
        "resz": body.resz,
        "brief": ((p.get("brief") or {}).get("uj") or None) if body.resz == "brief" else None,
        "forras": (p.get("brief") or {}).get("forras") if body.resz == "brief" else (
            "Lara (modell, a tapasztalat alapján)" if m.get("allapot") == "kesz" else "Lara (tapasztalat alapján)"
        ),
        "technika": [
            {k: t.get(k) for k in ("equipment_id", "nev", "kategoria", "qty", "track_mode", "indoklas", "szerep", "forras")}
            | {"helyettesiti": (t.get("helyettesiti") or {}).get("nev") if isinstance(t.get("helyettesiti"), dict) else None}
            for t in (p.get("technika") or [])
        ] if body.resz == "technika" else [],
        "meglevo_technika": len(p.get("meglevo_technika") or []),
        "figyelmeztetesek": figy[:10],
        "feladat_ertelmezes": m.get("feladat_ertelmezes"),
        "modell": m.get("allapot"),
        "hasonlo_forgatasok": len((ter.get("tapasztalat") or {}).get("hasonlo_forgatasok") or []),
    }


@router.post("/diszpo/{project_id}/tervezet")
def diszpo_tervezet_projektrol(
    project_id: int,
    body: DiszpoFeladatIn | None = None,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """A forgatás oldaláról: Lara-feladat (a nyitott diszpó-feladat újrahasználva)
    és rögtön a brief + technika tervezete, jóváhagyásra."""
    from app.models.project import Project

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="A forgatás nem található.")
    lezart = [s.value for s in LEZART_TASK_STATES]
    t = db.scalar(
        select(AdminTask).where(AdminTask.tipus == "diszpo", AdminTask.project_id == project.id,
                                AdminTask.allapot.notin_(lezart)).order_by(AdminTask.id.desc())
    )
    if t is None:
        t = AdminTask(
            tipus="diszpo", cim=f"Diszpó brief + technika: {project.nev}"[:300], allapot=TaskState.NEW.value,
            felelos_id=_uj_feladat_felelose(db, user.id), project_id=project.id, project_code_id=project.project_code_id,
            trust_level="L0", forras_referenciak={"diszpo_projekt": project.id, "letrehozta_id": user.id},
        )
        db.add(t)
        db.flush()
    b = body or DiszpoFeladatIn()
    return task_tervezet(t.id, TervezetIn(brief=b.brief, technika=b.technika, diszpo_szoveg=b.diszpo_szoveg), db=db, user=user)


@router.post("/tasks/{task_id}/diszpo/visszavonas")
def diszpo_visszavonas(
    task_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A végrehajtott diszpó-tervezet visszavonása: a Lara által hozzárendelt
    eszközök törlése / darabszám visszaállítása, és a korábbi brief visszaírása
    (ha azóta senki nem módosította)."""
    from app.admin_agent.diszpo_tervezo import ESZKOZ, visszavonas

    ex = db.scalar(
        select(ActionExecution)
        .join(ActionProposal, ActionProposal.id == ActionExecution.proposal_id)
        .where(ActionProposal.task_id == task_id, ActionProposal.eszkoz == ESZKOZ, ActionExecution.allapot == "succeeded")
        .order_by(ActionExecution.id.desc())
    )
    if ex is None:
        raise HTTPException(status_code=404, detail="Ennél a feladatnál nincs végrehajtott diszpó-tervezet.")
    if (ex.eredmeny or {}).get("visszavonva"):
        raise HTTPException(status_code=409, detail="Ezt már visszavontad.")
    try:
        ki = visszavonas(db, ex.eredmeny or {})
    except DiszpoHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ex.eredmeny = {**(ex.eredmeny or {}), "visszavonva": {"at": datetime.now(timezone.utc).isoformat(), "ki": user.id, **ki}}
    db.add(ActionTrace(task_id=task_id, szereplo="human", muvelet="diszpo_visszavonas", eroforras=ESZKOZ,
                       diff={"execution_id": ex.id, **ki}, eredmeny="kesz", tortent_at=datetime.now(timezone.utc)))
    db.commit()
    return ki


def _osszefogo_task(db: Session, task_id: int) -> AdminTask:
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    if t.tipus != "osszefogo":
        raise HTTPException(status_code=400, detail="Ez nem összefogó feladat.")
    return t


@router.get("/tasks/{task_id}/osszefogo")
def osszefogo_allapot(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Az összefogó feladat hatóköre, élő terve (konkrét teendők a teljes
    rendszerből) és a részfeladatok előrehaladása."""
    from app.admin_agent import osszefogo

    return osszefogo.allapot(db, _osszefogo_task(db, task_id))


@router.post("/tasks/{task_id}/osszefogo/ertelmezes")
def osszefogo_ertelmezes(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    from app.admin_agent import osszefogo

    t = _osszefogo_task(db, task_id)
    o = osszefogo.ertelmez(db, t)
    db.commit()
    return o


class HatokorIn(BaseModel):
    temak: list[str] | None = None
    idoszak: dict | None = None
    projektkodok: list[str] | None = None


@router.patch("/tasks/{task_id}/osszefogo/hatokor")
def osszefogo_hatokor(
    task_id: int,
    body: HatokorIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    from app.admin_agent import osszefogo

    t = _osszefogo_task(db, task_id)
    try:
        o = osszefogo.hatokor_modositas(db, t, body.model_dump(exclude_unset=True))
    except osszefogo.OsszefogoHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return o


@router.post("/tasks/{task_id}/osszefogo/bontas")
def osszefogo_bontas(
    task_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """Részfeladatok létrehozása a terv tételeiből (idempotens). Üzleti rekordot
    nem ír: a részfeladatok a szokásos javaslat → jóváhagyás úton mennek tovább."""
    from app.admin_agent import osszefogo

    t = _osszefogo_task(db, task_id)
    try:
        ki = osszefogo.bontas(db, t, user)
    except osszefogo.OsszefogoHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ki


@router.post("/tasks/{task_id}/osszefogo/frissites")
def osszefogo_frissites(
    task_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    from app.admin_agent import osszefogo

    a = osszefogo.frissites(db, _osszefogo_task(db, task_id))
    db.commit()
    return a


# ── Lara eszköz-ismerete (mi micsoda, mire jó, mi hasonló) ────────────────────


def _eszkoz_or_404(db: Session, equipment_id: int):
    from app.models.equipment import Equipment

    e = db.get(Equipment, equipment_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Az eszköz nem található.")
    return e


@router.get("/eszkozok/ismeret")
def eszkoz_ismeret_lista(
    q: str | None = Query(default=None, max_length=100),
    funkcio: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=300, ge=1, le=2000),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Lara eszköz-ismerete az eszköztörzsre: szerep, altípus, gyújtótáv,
    „mire jó”, és hogy a profil honnan van (szabály / modell / ember). Csak olvas."""
    from app.admin_agent.eszkoz_ismeret import FUNKCIOK, profilok, szerep_szoveg
    from app.admin_agent.diszpo_tervezo import hasznalhato
    from app.models.equipment import Equipment

    lek = select(Equipment).order_by(Equipment.kategoria, Equipment.nev)
    if q:
        lek = lek.where(Equipment.nev.ilike(f"%{q.strip()}%"))
    eszk = db.scalars(lek.limit(limit)).all()
    prof = profilok(db, list(eszk))
    elemek = [
        {"id": e.id, "nev": e.nev, "kategoria": e.kategoria, "hasznalhato": hasznalhato(e),
         "szerep": szerep_szoveg(prof[e.id]), **prof[e.id]}
        for e in eszk if not funkcio or prof[e.id]["funkcio"] == funkcio
    ]
    return {"funkciok": FUNKCIOK, "elemek": elemek,
            "forrasok": {f: sum(1 for x in elemek if x["forras"] == f) for f in ("szabaly", "modell", "ember")}}


@router.get("/eszkozok/{equipment_id}/ismeret")
def eszkoz_ismeret(
    equipment_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Egy eszköz profilja és a hozzá leginkább hasonló (helyettesítésre
    alkalmas) eszközök."""
    from app.admin_agent.eszkoz_ismeret import hasonlo_eszkozok, profil, szerep_szoveg

    e = _eszkoz_or_404(db, equipment_id)
    p = profil(db, e)
    return {"id": e.id, "nev": e.nev, "kategoria": e.kategoria, "szerep": szerep_szoveg(p), "profil": p,
            "hasonlok": hasonlo_eszkozok(db, e)}


class EszkozProfilIn(BaseModel):
    funkcio: str | None = None
    altipus: str | None = None
    marka: str | None = None
    gyujto_min: float | None = None
    gyujto_max: float | None = None
    fenyero: float | None = None
    bajonett: str | None = None
    mire_jo: str | None = Field(default=None, max_length=300)


@router.patch("/eszkozok/{equipment_id}/profil")
def eszkoz_profil_javitas(
    equipment_id: int,
    body: EszkozProfilIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Emberi javítás: mostantól ez Lara ismerete erről az eszközről (a modell
    sem írja felül). Csak Lara saját táblájába ír."""
    from app.admin_agent.eszkoz_ismeret import ProfilHiba, ember_javitas

    e = _eszkoz_or_404(db, equipment_id)
    try:
        p = ember_javitas(db, e, body.model_dump(exclude_unset=True), user)
    except ProfilHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.add(ActionTrace(task_id=None, szereplo="human", muvelet="eszkoz_profil_javitas", eroforras=f"equipment:{e.id}",
                       diff={"javitas": body.model_dump(exclude_unset=True), "employee_id": user.id}, eredmeny="kesz",
                       tortent_at=datetime.now(timezone.utc)))
    db.commit()
    return p


@router.delete("/eszkozok/{equipment_id}/profil", status_code=204)
def eszkoz_profil_visszaallitas(
    equipment_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A tárolt (modell / ember) profil törlése - újra a szabály alapú érvényes."""
    from app.admin_agent.eszkoz_ismeret import ember_javitas_torlese

    ember_javitas_torlese(db, _eszkoz_or_404(db, equipment_id))
    db.commit()


class AiProfilozasIn(BaseModel):
    limit: int = Field(default=40, ge=1, le=100)
    ujra: bool = False


@router.post("/eszkozok/ai-profilozas")
def eszkoz_ai_profilozas(
    body: AiProfilozasIn | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Kézi indítás: a modell pontosítja a még nem profilozott eszközöket
    (emberi profilt nem ír felül). Modell nélkül 400 - beállítás szükséges."""
    from app.admin_agent.eszkoz_ismeret import ProfilHiba, ai_profilozas

    b = body or AiProfilozasIn()
    try:
        ki = ai_profilozas(db, limit=b.limit, ujra=b.ujra)
    except ProfilHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ki


# ── Forgatás-ismeret: mi a feladat a forgatáson ─────────────────────────────


def _forgatas_or_404(db: Session, project_id: int):
    from app.models.project import Project

    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="A forgatás nem található.")
    return p


@router.get("/forgatasok/ismeret")
def forgatas_ismeret_attekintes(
    tipus: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Mit tud Lara a korábbi forgatásokról: feladat-típusonként hány forgatás,
    ebből hánynál ismert a kivitt technika, a felismerés forrása (szabály / AI /
    ember), és a forgatások listája. Csak olvas."""
    from app.admin_agent.forgatas_ismeret import attekintes

    return attekintes(db, tipus=tipus, q=q, limit=limit)


@router.get("/forgatasok/{project_id}/ismeret")
def forgatas_ismeret(
    project_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Egy forgatás felismert feladata, kivitt technikája szerepenként és amit
    Lara az ilyen feladatú korábbi forgatásokról tud. Csak olvas."""
    from app.admin_agent.forgatas_ismeret import forgatas_reszlet

    return forgatas_reszlet(db, _forgatas_or_404(db, project_id))


class ForgatasProfilIn(BaseModel):
    tipus: str | None = Field(default=None, max_length=30)
    tipusok: list[str] | None = None
    kimenetek: list[str] | None = None
    jellemzok: list[str] | None = None
    feladat_leiras: str | None = Field(default=None, max_length=400)


@router.patch("/forgatasok/{project_id}/feladat")
def forgatas_feladat_javitas(
    project_id: int,
    body: ForgatasProfilIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Emberi javítás: mostantól ez Lara tudása a forgatás feladatáról (a modell
    sem írja felül). Csak Lara saját táblájába ír, a forgatáshoz nem nyúl."""
    from app.admin_agent.forgatas_ismeret import ProfilHiba, ember_javitas

    p = _forgatas_or_404(db, project_id)
    try:
        pr = ember_javitas(db, p, body.model_dump(exclude_unset=True), user)
    except ProfilHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.add(ActionTrace(task_id=None, szereplo="human", muvelet="forgatas_feladat_javitas", eroforras=f"project:{p.id}",
                       diff={"javitas": body.model_dump(exclude_unset=True), "employee_id": user.id}, eredmeny="kesz",
                       tortent_at=datetime.now(timezone.utc)))
    db.commit()
    return pr


@router.delete("/forgatasok/{project_id}/feladat", status_code=204)
def forgatas_feladat_visszaallitas(
    project_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A tárolt (AI / ember) felismerés törlése - újra a szabály alapú érvényes."""
    from app.admin_agent.forgatas_ismeret import ember_javitas_torlese

    ember_javitas_torlese(db, _forgatas_or_404(db, project_id))
    db.commit()


class ForgatasAiTanulasIn(BaseModel):
    limit: int = Field(default=20, ge=1, le=60)
    ujra: bool = False


@router.post("/forgatasok/ai-tanulas")
def forgatas_ai_tanulas(
    body: ForgatasAiTanulasIn | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Kézi indítás: a modell végigolvas `limit` korábbi forgatást (a
    legutóbbiaktól visszafelé), és pontosítja a feladatukat. Emberi javítást
    nem ír felül. Modell nélkül 400 - beállítás szükséges."""
    from app.admin_agent.forgatas_ismeret import ProfilHiba, ai_tanulas

    b = body or ForgatasAiTanulasIn()
    try:
        ki = ai_tanulas(db, limit=b.limit, ujra=b.ujra)
    except ProfilHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ki


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
            tudas_fajta="eseti_magyarazat",
            bizonyitek_szint="forras",
            jovahagyta_id=user.id,
            jovahagyva_at=_most(),
        )
        db.add(m)
        db.flush()
        pelda_id = m.id
    # Gyors visszacsatolás (kapcsolóval, alapból ki): a javítás / magyarázat
    # ugyanebben a tranzakcióban a tartós sorba kerül (lásd visszacsatolas.py).
    from app.admin_agent.visszacsatolas import sorba

    sorba(db, "tudas" if csak_magyarazat else "korrekcio", pelda_id if csak_magyarazat else c.id)
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
            # A szabály aktuális verziójának SZAKMAI tesztje (ha van) — lásd szakmai_eval.py.
            from app.admin_agent.szakmai_eval import elesitesi_kapu

            ok, indok = elesitesi_kapu(db, r)
            if not ok:
                raise HTTPException(status_code=409, detail=indok)
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


def _kerdes_sor(k: LaraKerdes, user: Employee | None = None) -> dict:
    from app.admin_agent.nyomozas import KULCS, lathato

    ktx = dict(k.kontextus or {})
    valasz_szoveg = k.valasz_szoveg
    # Lara utánanézése a futtató jogosultságával készült — csak neki látszik.
    if KULCS in ktx and not lathato(ktx.get(KULCS), user):
        ktx.pop(KULCS)
        if k.allapot == "lara_valaszolt":
            valasz_szoveg = None
    return {
        "id": k.id,
        "tipus": k.tipus,
        "allapot": k.allapot,
        "partner_nev": k.partner_nev,
        "kerdes": k.kerdes,
        "kontextus": ktx,
        "valasz_tipus": k.valasz_tipus,
        "valasz_szoveg": valasz_szoveg,
        "megvalaszolva_at": k.megvalaszolva_at.isoformat() if k.megvalaszolva_at else None,
        "szabaly_id": k.szabaly_id,
        "letrehozva": k.created_at.isoformat() if k.created_at else None,
    }


@router.post("/self-check")
def onellenorzes_inditas(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
    vizsga: str = Query(default="minta", pattern="^(minta|teljes)$"),
):
    """Lara önellenőrzése most: előbb a friss rögzítések visszajátszása, majd a
    jelenlegi tudással „vak" jóslat minden rögzített számlára és lezárt eseti
    szerződés/TIG döntésre (Utókövetés), összevetés a valósággal; ahol nem érti
    az eltérést, kérdez. Mellette VIZSGA a tanulás kezdete előtti adaton: egy
    véletlen adag (`vizsga=minta`), vagy a teljes régi adat (`vizsga=teljes`).
    Üzleti rekord nem változik."""
    from app.admin_agent.onellenorzes import onellenorzes
    from app.admin_agent.visszajatszas import visszajatszas

    from app.admin_agent.megerosites import futtat

    vj = visszajatszas(db)
    eredmeny = onellenorzes(db, trigger="onellenorzes:kezi", teljes_vizsga=vizsga == "teljes")
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
    import logging

    from app.admin_agent.rendszer import rendszer_figyeles

    try:
        eredmeny = rendszer_figyeles(db, trigger="rendszer:kezi")
    except Exception as exc:  # noqa: BLE001 — érthető hiba a felületnek a néma 500 helyett
        db.rollback()
        logging.getLogger(__name__).exception("A rendszer kézi átnézése sikertelen.")
        raise HTTPException(
            status_code=500,
            detail=f"A rendszer átnézése hibára futott ({type(exc).__name__}: {str(exc)[:200]}).",
        ) from exc
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
    user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
    allapot: str = Query(default="nyitott"),
    limit: int = Query(default=100, ge=1, le=500),
):
    from app.admin_agent.nyomozas import bekapcsolva, elerheto, statisztika

    felt = [] if allapot == "mind" else [LaraKerdes.allapot == allapot]
    sorok = db.scalars(select(LaraKerdes).where(*felt).order_by(LaraKerdes.id.desc()).limit(limit)).all()
    return {
        "elemek": [_kerdes_sor(k, user) for k in sorok],
        "nyomozas": {**statisztika(db), "bekapcsolva": bekapcsolva(db), "elerheto": elerheto()},
    }


@router.post("/questions/{kerdes_id}/reopen")
def kerdes_visszanyitas(
    kerdes_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """„Nem így" — Lara magától adott válaszát a felelős nem fogadja el: a
    kérdés újra nyitott, és Lara a felelőstől várja a választ."""
    from app.admin_agent.nyomozas import KULCS

    _csak_a_felelos_donthet(db, user)
    k = db.get(LaraKerdes, kerdes_id)
    if k is None:
        raise HTTPException(status_code=404, detail="A kérdés nem található.")
    if k.allapot != "lara_valaszolt":
        raise HTTPException(status_code=409, detail="Ezt a kérdést nem Lara válaszolta meg magától.")
    k.allapot, k.valasz_tipus, k.valasz_szoveg, k.megvalaszolva_at = "nyitott", None, None, None
    ktx = dict(k.kontextus or {})
    if KULCS in ktx:
        ktx[KULCS] = {**ktx[KULCS], "onallo": False, "elutasitva": True, "elfogadva": False}
    k.kontextus = ktx
    db.commit()
    return {"kerdes": _kerdes_sor(k, user)}


@router.post("/questions/{kerdes_id}/investigate")
def kerdes_nyomozas(
    kerdes_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Lara utánanéz a kérdésnek — az AI asszisztens CSAK OLVASÓ eszközeivel és
    tudásával, a kérő jogosultságával (lásd admin_agent/nyomozas.py). Semmit
    nem módosít; a válasza javaslat, a kérdést ember zárja le."""
    from app.admin_agent.nyomozas import elerheto, nyomoz
    from app.admin_agent.settings_service import leallitva

    _csak_a_felelos_donthet(db, user)
    if leallitva(db):
        raise HTTPException(status_code=409, detail="Lara le van állítva (vészleállítás).")
    if not elerheto():
        raise HTTPException(status_code=409, detail="Beállítás szükséges: a szerveren nincs Gemini-kulcs.")
    k = db.get(LaraKerdes, kerdes_id)
    if k is None:
        raise HTTPException(status_code=404, detail="A kérdés nem található.")
    if k.allapot != "nyitott":
        raise HTTPException(status_code=409, detail="Erre a kérdésre már válaszoltak.")
    nyomoz(db, k, user)
    db.commit()
    return {"kerdes": _kerdes_sor(k, user)}


class ValaszIn(BaseModel):
    #: mindig | kivetel | magyarazat | hibas | elvet
    valasz_tipus: str
    magyarazat: str | None = Field(default=None, max_length=2000)
    #: „mindig így" esetén: élesítse-e azonnal a szabályt (joggal + sikeres eval mellett).
    elesit: bool = True
    #: A válasz Lara saját utánanézésének elfogadása (statisztikához).
    lara_valasza: bool = False


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
    if k.allapot == "lara_valaszolt":
        # Lara magától megválaszolta — a felelős most dönt róla (elfogadja
        # vagy a saját válaszát adja): a kérdés újra nyitottként megy tovább.
        _csak_a_felelos_donthet(db, user)
        k.allapot = "nyitott"
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
    from app.admin_agent.nyomozas import elfogadas_jelolese

    elfogadas_jelolese(k, body.lara_valasza)
    from app.admin_agent.visszacsatolas import sorba

    sorba(db, "kerdes_valasz", k.id)
    db.commit()
    return {"kerdes": _kerdes_sor(k, user), **eredmeny}


@router.get("/gemini")
def gemini_allapot(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Lara Gemini-kapcsolata: ugyanaz a kulcs és modell, mint az AI
    asszisztensé; mely Lara-funkciók használják, és a Gemini-tanulás eredménye.
    Titkot nem ad vissza (csak azt, hogy van-e kulcs)."""
    from app.admin_agent.gemini_tanulas import allapot

    return allapot(db)


@router.post("/gemini/test")
def gemini_teszt(
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Egy apró, valódi modellhívás: él-e a Gemini-kapcsolat."""
    from app.admin_agent.gemini_tanulas import kapcsolat_teszt

    return kapcsolat_teszt()


@router.post("/gemini/learn")
def gemini_tanulas_most(
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Gyorsított tanulás most a Geminivel: partner-profilok és önreflexió.
    Minden eredmény jelölt / függő szabály — élesíteni ember tud."""
    from app.admin_agent.gemini_tanulas import futtat
    from app.admin_agent.settings_service import leallitva

    _csak_a_felelos_donthet(db, user)
    if leallitva(db):
        raise HTTPException(status_code=409, detail="Lara le van állítva (vészleállítás).")
    try:
        eredmeny = futtat(db, trigger="kezi")
    except Exception as exc:  # noqa: BLE001 — érthető hibaüzenet a felületnek
        import logging

        db.rollback()
        logging.getLogger(__name__).exception("Lara Gemini-tanulása sikertelen.")
        raise HTTPException(status_code=500, detail=f"A Gemini-tanulás nem sikerült: {type(exc).__name__}") from exc
    db.commit()
    return eredmeny


@router.post("/experience")
def tapasztalas_most(
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Tapasztalás most: tények a teljes adattörténetből + a Gemini állításai,
    amelyeket Lara a teljes adaton ellenőriz. Csak Lara saját tábláiba ír."""
    from app.admin_agent.settings_service import leallitva
    from app.admin_agent.tapasztalas import futtat

    _csak_a_felelos_donthet(db, user)
    if leallitva(db):
        raise HTTPException(status_code=409, detail="Lara le van állítva (vészleállítás).")
    try:
        eredmeny = futtat(db, trigger="kezi", kenyszeritett=True)
    except Exception as exc:  # noqa: BLE001 — érthető hibaüzenet a felületnek
        import logging

        db.rollback()
        logging.getLogger(__name__).exception("Lara tapasztalás-köre sikertelen.")
        raise HTTPException(status_code=500, detail=f"A tapasztalás nem sikerült: {type(exc).__name__}") from exc
    db.commit()
    return eredmeny


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
    else:
        # A kézikönyv-szakaszoknak saját nézetük és jóváhagyásuk van (/kezikonyv).
        felt.append(MemoryChunk.hatokor != "kezikonyv")
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
    from app.admin_agent.visszacsatolas import sorba

    sorok = db.scalars(select(MemoryChunk).where(MemoryChunk.id.in_(body.ids))).all()
    kesz = 0
    kihagyott = 0
    for m in sorok:
        if m.hatokor == "kezikonyv":
            # A kézikönyv csak a saját (verziózó) útján hagyható jóvá / vethető el.
            kihagyott += 1
            continue
        if body.muvelet == "jovahagy":
            if m.visszavont:
                kihagyott += 1
                continue
            m.ervenyes = True
            m.minosites = "jovahagyott"
            m.jovahagyta_id, m.jovahagyva_at = user.id, _most()
            sorba(db, "tudas", m.id)
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
    if m.hatokor == "kezikonyv":
        raise HTTPException(status_code=409, detail="Kézikönyv-szakasz a Kézikönyv nézetben kezelhető.")
    if payload.ervenyes is True:
        check_page_action(db, user, PAGE, "delete")
        if m.visszavont:
            raise HTTPException(status_code=409, detail="Elvetett példa nem hagyható jóvá.")
        m.ervenyes = True
        m.minosites = "jovahagyott"
        m.jovahagyta_id, m.jovahagyva_at = user.id, _most()
        from app.admin_agent.visszacsatolas import sorba

        sorba(db, "tudas", m.id)
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


@router.post("/modell/ellenorzes")
def modell_ellenorzes(
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Élő kapcsolat-próba a nyelvi modellel (Beállítások gomb): egy egyszerű
    hívás, majd egy Lara eszközeivel, a beszélgetés beállításaival. Adatot nem
    olvas és nem ír; a válasz a hiba emberi, titokmentes leírása."""
    from app.admin_agent import nyomozas

    return nyomozas.modell_ellenorzes()


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
        regi = dict(s.limitek or {})
        uj = dict(payload.limitek)
        # Szerveroldali kulcsok: a felhasználók SAJÁT megszólítása (csak ők
        # állíthatják, lásd /chat/preferences) és az automatikus elemzés
        # bekapcsolásának ideje - a beállítás-mentés nem írhatja felül.
        for kulcs in ("megszolitasok", "auto_szamla_elemzes_tol"):
            if kulcs in regi:
                uj[kulcs] = regi[kulcs]
            else:
                uj.pop(kulcs, None)
        if uj.get("auto_szamla_elemzes") is True and regi.get("auto_szamla_elemzes") is not True:
            # Csak a bekapcsolás UTÁN érkezett számlákat elemzi (lásd visszacsatolas.py).
            uj["auto_szamla_elemzes_tol"] = _most().isoformat()
        s.limitek = uj
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
