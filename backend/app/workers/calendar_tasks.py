"""Percenkénti Google Naptár -> Projekt szinkron - lásd
services/google_calendar.py a tényleges logikáért. Ez az EGYETLEN igazi
periodikus (Celery Beat) feladat a rendszerben (a többi háttérmunka vagy
admin-gombbal indított, vagy egy konkrét eseményhez `eta`-val időzített, lásd
dispo_tasks.py fejléce) - a beat schedule-t itt regisztráljuk a meglévő,
megosztott celery_app példányon (lásd portal_tasks.py), hogy ne kelljen külön
Railway service-t indítani csak ehhez: a worker "-B" flaggel indítva
(embedded beat) magába foglalja ezt is - lásd railway.worker.json."""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.services.google_calendar import CalendarNotConfiguredError, sync_hype_calendar
from app.workers.portal_tasks import celery_app

logger = logging.getLogger(__name__)

celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "calendar-sync-hype-calendar": {
        "task": "calendar.sync_hype_calendar",
        "schedule": 60.0,
    },
}


@celery_app.task(name="calendar.sync_hype_calendar")
def sync_hype_calendar_task() -> dict | None:
    db = SessionLocal()
    try:
        return sync_hype_calendar(db)
    except CalendarNotConfiguredError:
        # Amíg nincs beállítva a GOOGLE_CALENDAR_OAUTH_TOKEN_JSON/
        # GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON, ez minden percben lefutna -
        # debug szinten logoljuk (ne spammelje az error logot percenként).
        logger.debug("Naptár szinkron kihagyva: nincs Google Naptár hitelesítés beállítva.")
        return None
    except Exception:
        logger.exception("Naptár szinkron sikertelen.")
        raise
    finally:
        db.close()
