"""Admin-Ágens API (Fázis B/C alap). Az `/admin-agent` oldal jogosultságával.

BIZTONSÁGOS ALAPÁLLÁS: ezek a végpontok NEM hajtanak végre üzleti/külső
mellékhatást (L0). A task-létrehozás és -szerkesztés belső munkaszervezés; a
jóváhagyás-döntés csak rögzül (a végrehajtó réteg a következő fázis). Minden
mellékhatásos végrehajtás a policy engine-en (admin_agent.policy) fog átmenni.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.admin_agent.executor import execute_approved
from app.admin_agent.pipeline_szamla import arnyek_elemzes
from app.admin_agent.settings_service import get_settings
from app.core.database import get_db
from app.core.security import Role, require_page_action
from app.models.admin_agent import (
    ActionExecution,
    ActionProposal,
    ActionTrace,
    AdminTask,
    AgentRun,
    Approval,
    Correction,
)
from app.models.bejovo_szamla import BejovoSzamla
from app.models.employee import Employee

router = APIRouter(prefix="/admin-agent", tags=["admin-agent"])

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
        felelos_id=payload.felelos_id,
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
    műveletet: az ágens csak elemez és javaslatot rögzít a policy engine
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
    """A feladat teljes, olvasható idővonala: ügynökfutások, nyomvonal-
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
    """A feladat újraelemzése az ágenssel (L0-biztos: nincs mellékhatás). Jelenleg
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


class CorrectionIn(BaseModel):
    proposal_id: int | None = None
    javitott: dict
    magyarazat: str | None = None
    #: besorolando / egyszeri_kivetel / stilus / tenyszeru_hiba / uj_uzleti_adat
    tipus: str | None = None


@router.post("/tasks/{task_id}/corrections")
def task_correction(
    task_id: int,
    payload: CorrectionIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Emberi javítás rögzítése (tanulási jel). NEM aktivál szabályt — csak
    `correction`-t hoz létre `uj` feldolgozási állapotban, amit a háttér-tanuló
    (F fázis) dolgoz fel emberi jóváhagyás mellett."""
    t = db.get(AdminTask, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    eredeti = None
    if payload.proposal_id is not None:
        p = db.get(ActionProposal, payload.proposal_id)
        if p is None or p.task_id != task_id:
            raise HTTPException(status_code=404, detail="A javaslat nem ehhez a feladathoz tartozik.")
        eredeti = dict(p.payload)
    tipus = payload.tipus if payload.tipus in {c.value for c in CorrectionType} else CorrectionType.BESOROLANDO.value
    mezo_diff = _mezo_diff(eredeti or {}, payload.javitott)
    c = Correction(
        task_id=task_id,
        proposal_id=payload.proposal_id,
        eredeti=eredeti,
        javitott=payload.javitott,
        mezo_diff=mezo_diff,
        javito_employee_id=user.id,
        magyarazat=(payload.magyarazat or "").strip() or None,
        tipus=tipus,
        feldolgozas_allapot="uj",
    )
    db.add(c)
    db.commit()
    return {"correction_id": c.id, "tipus": c.tipus, "mezo_diff": mezo_diff}


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
    }


class SettingsPatchIn(BaseModel):
    module_enabled: bool | None = None
    side_effects_enabled: bool | None = None
    engedett_forrasok: dict | None = None
    limitek: dict | None = None


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
    s.modositotta_employee_id = user.id
    db.commit()
    return {
        "module_enabled": s.module_enabled,
        "side_effects_enabled": s.side_effects_enabled,
        "kill_switch": s.kill_switch,
        "kill_switch_indok": s.kill_switch_indok,
        "engedett_forrasok": s.engedett_forrasok or {},
        "limitek": s.limitek or {},
    }


class PauseIn(BaseModel):
    indok: str | None = None


@router.post("/pause")
def veszleallitas_be(
    payload: PauseIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Globális vészleállítás BE. Ezt a policy engine minden mellékhatásos
    lépés előtt ellenőrzi. A már elindult, nem megszakítható külső műveleteket
    ez NEM vonja vissza."""
    s = get_settings(db)
    s.kill_switch = True
    s.kill_switch_indok = (payload.indok or "").strip() or None
    s.modositotta_employee_id = user.id
    db.commit()
    return {"kill_switch": True, "indok": s.kill_switch_indok}


@router.post("/resume")
def veszleallitas_ki(
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    s = get_settings(db)
    s.kill_switch = False
    s.kill_switch_indok = None
    s.modositotta_employee_id = user.id
    db.commit()
    return {"kill_switch": False}
