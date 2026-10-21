"""Diszpó utáni utókövető email - a forgatás vége után 12 órával kiküldött
kérdőív-kérő email, ugyanabba a Gmail-szálba fűzve, mint maga a diszpó (lásd
services/dispo.py). A pontos időpont a diszpó kiküldésekor (send_diszpo)
ismert (forgatás dátuma), ezért ott ütemezzük be Celery `eta`-val - nincs
szükség külön 'beat' folyamatra, ami időnként átvizsgálná a projekteket."""

from __future__ import annotations

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.project import Project
from app.services.dispo import _SIGNATURE_HTML, _recipients, _subject
from app.services.google_email import send_message
from app.workers.portal_tasks import celery_app

_UTOKOVETES_HTML = """\
<p>Kedves Kollégák,</p>
<p>Köszönjük az ezen a diszpón végzett munkátokat!</p>
<p>
  Kérünk Benneteket, hogy a gördülékeny információ áramlás érdekében, az alábbi, rövid kérdőív
  kitöltésével segítsetek minket a forgatáson szerzett tapasztalataitok, információk megosztásával.
</p>
<p>
  <a href="{survey_url}" style="display:inline-block;padding:10px 20px;background:#111;color:#fff;
  text-decoration:none;border-radius:6px;font-family:Arial,sans-serif;font-size:14px;">
    Kérdőív kitöltése
  </a>
</p>
<p>Köszönettel,</p>
"""


@celery_app.task(name="dispo.send_utokovetes_email")
def send_utokovetes_email_task(project_id: int) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None or not project.utokoveto_token:
            return
        to_list = _recipients(project)
        if not to_list:
            return

        survey_url = f"{settings.frontend_base_url.rstrip('/')}/kerdoiv/{project.utokoveto_token}"
        html = _UTOKOVETES_HTML.format(survey_url=survey_url) + _SIGNATURE_HTML
        thread_id, _msg_id, rfc822 = send_message(
            to_list,
            _subject(project),
            html,
            thread_id=project.gmail_thread_id,
            in_reply_to=project.gmail_last_message_id,
            # ugyanabban a szálban válaszol, mint a diszpó - a feladónév is
            # ugyanaz kell legyen, különben a szál közepén nevet vált
            sender_name=settings.dispo_sender_name,
        )
        project.gmail_thread_id = thread_id or project.gmail_thread_id
        project.gmail_last_message_id = rfc822 or project.gmail_last_message_id
        db.commit()
    finally:
        db.close()
