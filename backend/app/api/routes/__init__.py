from fastapi import APIRouter

from app.api.routes.admin_calendar_sync import router as admin_calendar_sync_router
from app.api.routes.dispo_responsibles import router as dispo_responsibles_router
from app.api.routes.admin_import import router as admin_import_router
from app.api.routes.ai_assistant import router as ai_assistant_router
from app.api.routes.auth import router as auth_router
from app.api.routes.automation import router as automation_router
from app.api.routes.callsheets import router as callsheets_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.client_contracts import router as client_contracts_router
from app.api.routes.clients import contacts_router, router as clients_router
from app.api.routes.contracts import router as contracts_router
from app.api.routes.crew import rates_router, router as crew_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.detail_tabs import router as detail_tabs_router
from app.api.routes.equipment import assignments_router, router as equipment_router
from app.api.routes.entity_fields import router as entity_fields_router
from app.api.routes.field_visibility import router as field_visibility_router
from app.api.routes.finance import expenses_router, kp_forgalom_router, revenues_router, summary_router as finance_summary_router
from app.api.routes.internal_performance_certificates import router as internal_performance_certificates_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.performance_certificates import router as performance_certificates_router
from app.api.routes.portal import payments_router, router as portal_router
from app.api.routes.portal_admin import router as portal_admin_router
from app.api.routes.portal_public import downloads_router as portal_downloads_router, router as portal_public_router
from app.api.routes.postproduction import deliverable_actions_router, deliverables_router, feedback_router, timesheets_router
from app.api.routes.project_codes import router as project_codes_router
from app.api.routes.projects import router as projects_router
from app.api.routes.public_utokovetes import router as public_utokovetes_router
from app.api.routes.realtime import router as realtime_router
from app.api.routes.search import router as search_router
from app.api.routes.stocktake import router as stocktake_router
from app.api.routes.storage import folders_router, media_router
from app.api.routes.subcontractor_contracts import router as subcontractor_contracts_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.timeline import router as timeline_router
from app.api.routes.user_access import router as user_access_router
from app.api.routes.utokovetes_admin import router as utokovetes_admin_router

api_router = APIRouter()

# 1. Auth
api_router.include_router(auth_router)
# 2. Dashboard
api_router.include_router(dashboard_router)
# 3. Ügyfelek
api_router.include_router(clients_router)
api_router.include_router(contacts_router)
# 4-5. Project Codes / Projects
api_router.include_router(project_codes_router)
api_router.include_router(projects_router)
# 6. Crew (Employee + Rate)
api_router.include_router(crew_router)
api_router.include_router(rates_router)
# 7. Equipment
api_router.include_router(equipment_router)
api_router.include_router(assignments_router)
api_router.include_router(stocktake_router)
# 8. Timeline
api_router.include_router(timeline_router)
# 9. Storage
api_router.include_router(folders_router)
api_router.include_router(media_router)
# 10. Naptár / Diszpó
api_router.include_router(callsheets_router)
api_router.include_router(public_utokovetes_router)
# 11. Utómunka
api_router.include_router(deliverable_actions_router)
api_router.include_router(deliverables_router)
api_router.include_router(timesheets_router)
api_router.include_router(feedback_router)
# 12. Portál / Fizetés
api_router.include_router(portal_router)
api_router.include_router(payments_router)
api_router.include_router(portal_admin_router)
api_router.include_router(portal_public_router)
api_router.include_router(portal_downloads_router)
# 13. Pénzügyek
api_router.include_router(expenses_router)
api_router.include_router(revenues_router)
api_router.include_router(kp_forgalom_router)
api_router.include_router(finance_summary_router)
api_router.include_router(contracts_router)
api_router.include_router(subcontractor_contracts_router)
api_router.include_router(client_contracts_router)
api_router.include_router(performance_certificates_router)
api_router.include_router(internal_performance_certificates_router)
api_router.include_router(utokovetes_admin_router)
# 14. Kampányok
api_router.include_router(campaigns_router)
# Feladatok
api_router.include_router(tasks_router)
# Automation
api_router.include_router(automation_router)
# AI Assistant
api_router.include_router(ai_assistant_router)
# Beállítások: mező-láthatóság + oldal-hozzáférés (egyénenként) + admin fül-elrendezés
api_router.include_router(entity_fields_router)
api_router.include_router(field_visibility_router)
api_router.include_router(user_access_router)
api_router.include_router(detail_tabs_router)
# Értesítések
api_router.include_router(notifications_router)
# Admin: Notion import a böngészőből (railway ssh nélkül)
api_router.include_router(admin_import_router)
# Admin: HYPE CALENDAR naptár-szinkron kézi indítása/állapota
api_router.include_router(admin_calendar_sync_router)
api_router.include_router(dispo_responsibles_router)
# Globális kereső (TopBar "Keresés bármiben…")
api_router.include_router(realtime_router)
api_router.include_router(search_router)
