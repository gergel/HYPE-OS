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

from app.admin_agent.enums import LEZART_TASK_STATES, TaskState, TaskType
from app.admin_agent.settings_service import get_settings
from app.core.database import get_db
from app.core.security import Role, require_page_action
from app.models.admin_agent import AdminTask, Approval, ActionProposal
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
                "letrehozva": a.created_at.isoformat() if a.created_at else None,
            }
            for (a, p, t) in sorok
        ]
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
