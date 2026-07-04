"""Minden SQLAlchemy modell importja - ez adja a Base.metadata-t az Alembic autogenerate-hez."""

from app.core.database import Base
from app.models.callsheet import Callsheet
from app.models.campaign import Campaign
from app.models.client import Client, Contact
from app.models.contract import Contract, ContractType
from app.models.dashboard_config import DashboardConfig
from app.models.deliverable import Deliverable
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.feedback import Feedback
from app.models.field_visibility import FieldVisibilityConfig
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.media import Folder, Media
from app.models.notion_import import NotionImportMap
from app.models.portal import Brand, PaymentMode, Payment, Portal, PortalStatus
from app.models.project import Project, project_crew
from app.models.project_code import ProjectCode
from app.models.rate import Rate
from app.models.task import Task, task_employees
from app.models.timesheet import Timesheet
from app.models.timeline import TimelineEvent
from app.models.user_access import PageAccessConfig

__all__ = [
    "Base",
    "Callsheet",
    "Campaign",
    "Client",
    "Contact",
    "Contract",
    "ContractType",
    "DashboardConfig",
    "Deliverable",
    "Employee",
    "EmployeeType",
    "SystemRole",
    "Assignment",
    "Equipment",
    "TrackMode",
    "Feedback",
    "FieldVisibilityConfig",
    "Expense",
    "KpForgalom",
    "Revenue",
    "Folder",
    "Media",
    "NotionImportMap",
    "Brand",
    "PaymentMode",
    "Payment",
    "Portal",
    "PortalStatus",
    "Project",
    "project_crew",
    "ProjectCode",
    "Rate",
    "Task",
    "task_employees",
    "Timesheet",
    "TimelineEvent",
    "PageAccessConfig",
]
