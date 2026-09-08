from app.workers.portal_tasks import celery_app
from app.services.portal_exports import run_export, maintain_exports

@celery_app.task(name='portal.build_export', acks_late=True, reject_on_worker_lost=True,
                 soft_time_limit=21600, time_limit=21700)
def build_export(job_id):
    run_export(job_id)

@celery_app.task(name='portal.maintain_exports')
def cleanup_exports():
    maintain_exports()

celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    'portal-export-maintenance': {'task': 'portal.maintain_exports', 'schedule': 60.0},
}
