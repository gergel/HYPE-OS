"""Admin-Ágens háttérfeladatok (Celery Beat a megosztott celery_app-on).

* Éjszakai (02:00, szervezeti időzóna) háttér-tanuló (distill) — a korrekciókból
  szabály-/példa-JELÖLTEK; nem aktivál semmit.
* Heti értékelés (eval) — a biztonsági/pénzügyi invariánsok regressziós őre.

A beat itt regisztrálódik a meglévő workerre (lásd calendar_tasks.py), külön
Railway service nélkül (a worker "-B" flaggel embedded beatet is futtat). A
feladatok idempotensek: a distill csak az új korrekciókat dolgozza fel, a
kétszeres tudáskiadás ellen a jelölt→jóváhagyás→aktiválás lánc véd.
"""

from __future__ import annotations

import logging

from celery.schedules import crontab

from app.core.database import SessionLocal
from app.workers.portal_tasks import celery_app

logger = logging.getLogger(__name__)

# Europe/Budapest 02:00 — a Celery a beat időzónáját használja; ha a rendszer
# UTC-ben jár, ez UTC 02:00-nak felel meg. A pontos DST-kezelés a scheduler
# időzóna-beállításától függ (lásd docs/admin-agent/operations.md).
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "admin-agent-nightly-distill": {
        "task": "admin_agent.nightly_distill",
        "schedule": crontab(hour=2, minute=0),
    },
    "admin-agent-weekly-eval": {
        "task": "admin_agent.weekly_eval",
        # Hétfő 03:00.
        "schedule": crontab(hour=3, minute=0, day_of_week=1),
    },
}


@celery_app.task(name="admin_agent.nightly_distill")
def nightly_distill_task() -> dict | None:
    """A háttér-tanuló futtatása. Csak akkor dolgozik, ha a modul engedélyezett
    (a biztonságos alapállásban kihagyja — nem gyűjt/alakít semmit)."""
    from app.admin_agent.learning import distill
    from app.admin_agent.settings_service import get_settings

    db = SessionLocal()
    try:
        if not get_settings(db).module_enabled:
            logger.debug("Admin-Ágens distill kihagyva: a modul ki van kapcsolva.")
            return None
        lr = distill(db, trigger="nightly")
        db.commit()
        return {"learning_run_id": lr.id, "feldolgozott": lr.feldolgozott_korrekciok}
    except Exception:
        db.rollback()
        logger.exception("Admin-Ágens éjszakai distill sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.weekly_eval")
def weekly_eval_task() -> dict | None:
    """Heti teljes értékelés. A beépített biztonsági eseteket mindig ellenőrzi
    (a modul állapotától függetlenül — ez regressziós védelem)."""
    from app.admin_agent.evals import run_eval, safety_esetek_magveto

    db = SessionLocal()
    try:
        safety_esetek_magveto(db)
        run = run_eval(db)
        db.commit()
        return {"eval_run_id": run.id, "atment": run.atment, "kritikus_hiba": run.kritikus_hiba}
    except Exception:
        db.rollback()
        logger.exception("Admin-Ágens heti eval sikertelen.")
        raise
    finally:
        db.close()
