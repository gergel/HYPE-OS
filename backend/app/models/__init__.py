"""Minden SQLAlchemy modell importja - ez adja a Base.metadata-t az Alembic autogenerate-hez."""

from app.core.database import Base
from app.models.belsos_idoszak import BelsosIdoszak
from app.models.callsheet import Callsheet
from app.models.calendar_sync import CalendarSyncState
from app.models.campaign import Campaign
from app.models.client import Client, Contact
from app.models.contract import Contract, ContractTetel, ContractType
from app.models.dashboard_config import DashboardConfig
from app.models.deliverable import Deliverable, deliverable_contacts
from app.models.deliverable_comment import DeliverableComment
from app.models.deliverable_status import DeliverableBoardConfig, DeliverableStatusConfig
from app.models.detail_section_order import DetailSectionOrder
from app.models.detail_tab import DetailTabConfig
from app.models.document_attachment import DocumentAttachment
from app.models.dispo_responsible import DispoResponsible, DispoSide
from app.models.diszpo_tabla import DiszpoCella, DiszpoMunkalap, DiszpoOszlop, DiszpoSor
from app.models.employee import BelsosJogviszony, Employee, EmployeeType, SystemRole
from app.models.employee_document import EmployeeDocument
from app.models.employee_monthly_item import EmployeeMonthlyItem
from app.models.entity_field import CustomFieldDef, CustomFieldValue, EntityFieldConfig
from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.feedback import Feedback, VisszajelzesAllapot
from app.models.field_visibility import FieldVisibilityConfig
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.internal_performance_certificate import (
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.models.auto import Auto
from app.models.keret_modositas import KeretModositas
from app.models.kotelezettseg import (
    Kotelezettseg,
    KotelezettsegCiklus,
    KotelezettsegIdoszak,
    KotelezettsegTipus,
)
from app.models.media import Folder, Media
from app.models.notification import Notification
from app.models.notion_import import NotionImportMap
from app.models.performance_certificate import (
    PerformanceCertificate,
    PerformanceCertificateInvoice,
    PerformanceCertificateTetel,
)
from app.models.post_shoot_feedback import PostShootFeedback
from app.models.portal import (
    Brand,
    PaymentMode,
    Payment,
    Portal,
    PortalFolder,
    PortalImage,
    PortalStatus,
    PortalVideo,
)
from app.models.project import Project, project_crew
from app.models.project_szamlazo import ProjectSzamlazo
from app.models.project_code import ProjectCode
from app.models.rate import Rate
from app.models.stocktake import StocktakeItem, StocktakeSession
from app.models.task import Task, task_employees
from app.models.timesheet import Timesheet
from app.models.timeline import TimelineEvent
from app.models.user_access import PageAccessConfig
from app.models.krumpello import (
    KrumpelloDolgozo,
    KrumpelloKiadas,
    KrumpelloMunkaora,
    KrumpelloNap,
)
from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig
from app.models.vagoi_jatek import (
    VagoEllenorzesEsemeny,
    VagoJatekHonap,
    VagoJatekNap,
)
from app.models.vallalkozas import Vallalkozas, VallalkozasTag

__all__ = [
    "Base",
    "Callsheet",
    "CalendarSyncState",
    "Campaign",
    "Client",
    "Contact",
    "Contract",
    "ContractType",
    "DashboardConfig",
    "DocumentAttachment",
    "EmployeeMonthlyItem",
    "Deliverable",
    "DiszpoCella",
    "DiszpoMunkalap",
    "DiszpoOszlop",
    "DiszpoSor",
    "deliverable_contacts",
    "DeliverableBoardConfig",
    "DeliverableStatusConfig",
    "DeliverableComment",
    "DetailSectionOrder",
    "DetailTabConfig",
    "DispoResponsible",
    "DispoSide",
    "Employee",
    "EmployeeType",
    "SystemRole",
    "EmployeeDocument",
    "Assignment",
    "Equipment",
    "TrackMode",
    "Feedback",
    "FieldVisibilityConfig",
    "GoogleOAuthToken",
    "Expense",
    "KpForgalom",
    "Revenue",
    "InternalPerformanceCertificate",
    "InternalPerformanceCertificateInvoice",
    "Folder",
    "Media",
    "Notification",
    "NotionImportMap",
    "PerformanceCertificate",
    "PerformanceCertificateInvoice",
    "PostShootFeedback",
    "Brand",
    "PaymentMode",
    "Payment",
    "Portal",
    "PortalFolder",
    "PortalImage",
    "PortalStatus",
    "PortalVideo",
    "Project",
    "project_crew",
    "BelsosIdoszak",
    "BelsosJogviszony",
    "ProjectSzamlazo",
    "ContractTetel",
    "PerformanceCertificateTetel",
    "KrumpelloDolgozo",
    "KrumpelloKiadas",
    "KrumpelloMunkaora",
    "KrumpelloNap",
    "KeretModositas",
    "MegrendeloiSzerzodes",
    "MegrendeloiTig",
    "VagoEllenorzesEsemeny",
    "VagoJatekHonap",
    "VagoJatekNap",
    "Vallalkozas",
    "VallalkozasTag",
    "ProjectCode",
    "Rate",
    "StocktakeItem",
    "StocktakeSession",
    "Task",
    "task_employees",
    "Timesheet",
    "TimelineEvent",
    "PageAccessConfig",
]
