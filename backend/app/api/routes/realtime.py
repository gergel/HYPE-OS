"""Változás-ujjlenyomat végpont a felület háttérben történő frissítéséhez.

A böngésző néhány másodpercenként megkérdezi, hogy a NÉZETT témákban
(projektek, hozzászólások, értesítések, ...) történt-e változás. A válasz csak
egy rövid ujjlenyomat témánként - `sorok száma:legutolsó módosítás` -, tehát
tartalmat NEM ad vissza, és a lekérdezés két olcsó aggregátum. Ha az
ujjlenyomat változik, a frontend tölti újra a tényleges adatokat
(router.refresh(), lásd frontend/lib/live.tsx) - így a drága újratöltés csak
akkor fut le, amikor tényleg történt valami.

Miért lekérdezés és nem SSE/WebSocket: a HYPE OS több uvicorn worker-rel futhat
és nincs közös üzenetsor, amin a workerek értesíthetnék egymást egy írásról -
egy nyitva tartott stream csak akkor tudna friss adatot adni, ha ő maga is az
adatbázist kérdezgetné, viszont közben lekötne egy kapcsolatot böngészőfülenként.

A sorok számát is nézzük, nem csak a max(updated_at)-et: TÖRLÉSKOR a legutolsó
módosítás időpontja változatlan maradhat (a törölt sor egyszerűen eltűnik), a
darabszám viszont csökken."""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.callsheet import Callsheet
from app.models.campaign import Campaign
from app.models.client import Client, Contact
from app.models.contract import Contract
from app.models.deliverable import Deliverable
from app.models.deliverable_comment import DeliverableComment
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment
from app.models.feedback import Feedback
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.flora_komment import FloraKomment
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.notification import Notification
from app.models.performance_certificate import PerformanceCertificate
from app.models.portal import Portal
from app.models.post_shoot_feedback import PostShootFeedback
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_code_comment import ProjectCodeComment
from app.models.rate import Rate
from app.models.stocktake import StocktakeSession
from app.models.task import Task
from app.models.timesheet import Timesheet

router = APIRouter(prefix="/realtime", tags=["realtime"])

# Egy kérésben ennyi témát nézünk meg. Egy oldalnak ennél jóval kevesebb kell;
# a korlát csak azt akadályozza meg, hogy egy elgépelt hívás az összes táblát
# végigszámolja.
MAX_TOPICS = 16


@dataclass(frozen=True)
class Topic:
    """Egy figyelhető téma: melyik tábla, és hogyan szűkíthető.

    `scope_column`: a "téma:azonosító" alakú kérésekhez (pl. `comments:12` =
    a 12-es utómunka hozzászólásai) - enélkül egy chat minden más chat
    üzenetére is frissülne.

    `user_column`: a felhasználóhoz kötött témák (értesítések) MINDIG a
    bejelentkezett emberre szűkülnek, akkor is, ha a kérés nem kérte."""

    model: type
    scope_column: str | None = None
    user_column: str | None = None


TOPICS: dict[str, Topic] = {
    "projects": Topic(Project),
    "projectCodes": Topic(ProjectCode),
    "deliverables": Topic(Deliverable),
    "comments": Topic(DeliverableComment, scope_column="deliverable_id"),
    "documentAttachments": Topic(DocumentAttachment),
    "projectCodeComments": Topic(ProjectCodeComment, scope_column="project_code_id"),
    "floraComments": Topic(FloraKomment, scope_column="flora_feladat_id"),
    "notifications": Topic(Notification, user_column="employee_id"),
    "tasks": Topic(Task),
    "employees": Topic(Employee),
    "rates": Topic(Rate),
    "equipment": Topic(Equipment),
    "assignments": Topic(Assignment, scope_column="project_id"),
    "stocktakes": Topic(StocktakeSession),
    "clients": Topic(Client),
    "contacts": Topic(Contact),
    "campaigns": Topic(Campaign),
    "contracts": Topic(Contract),
    "expenses": Topic(Expense),
    "revenues": Topic(Revenue),
    "kpForgalmak": Topic(KpForgalom),
    "performanceCertificates": Topic(PerformanceCertificate),
    "internalPerformanceCertificates": Topic(InternalPerformanceCertificate),
    "timesheets": Topic(Timesheet),
    "feedbacks": Topic(Feedback),
    "postShootFeedbacks": Topic(PostShootFeedback),
    "callsheets": Topic(Callsheet, scope_column="project_id"),
    "portals": Topic(Portal),
}


def _fingerprint(db: Session, topic: Topic, scope: str | None, user_id: int) -> str:
    stmt = select(func.count(topic.model.id), func.max(topic.model.updated_at))
    if topic.user_column:
        stmt = stmt.where(getattr(topic.model, topic.user_column) == user_id)
    if scope and topic.scope_column:
        # Nem szám azonosítóra nem szűrünk, hanem a teljes témát adjuk vissza -
        # így egy hibás kérés is legfeljebb túl gyakori frissítést okoz.
        if scope.isdigit():
            stmt = stmt.where(getattr(topic.model, topic.scope_column) == int(scope))
    count, latest = db.execute(stmt).one()
    return f"{count}:{latest.isoformat() if latest else '-'}"


@router.get("/changes")
def get_changes(
    topics: str = Query(..., description="Vesszővel elválasztott témák, pl. 'projects,comments:12'"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
) -> dict[str, str]:
    """Téma -> ujjlenyomat. A bejelentkezés kötelező, de a válasz nem tartalmaz
    rekord-adatot (csak darabszámot és időbélyeget), ezért nincs külön
    oldal-jogosultság ellenőrzés: aki a témát látni is akarja, azt a tényleges
    adatlekérésnél úgyis a szokásos jogosultság-ellenőrzés fogadja."""
    requested = [t.strip() for t in topics.split(",") if t.strip()]
    if not requested:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nincs megadva téma.")
    if len(requested) > MAX_TOPICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Egyszerre legfeljebb {MAX_TOPICS} téma kérdezhető le.",
        )

    result: dict[str, str] = {}
    for entry in requested:
        name, _, scope = entry.partition(":")
        topic = TOPICS.get(name)
        if topic is None:
            continue
        result[entry] = _fingerprint(db, topic, scope or None, current_user.id)
    return result
