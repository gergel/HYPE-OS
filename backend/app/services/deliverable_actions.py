"""Az Utómunka (Deliverable) oldal kapcsolatai és gombjai: ki hozta létre / kire
van kiosztva, vinyó-lista, Start/Stop időmérés, megrendelői kontaktok +
levezetett email-lista, "Visszajelzés küldése" gomb (a felhasználó által
küldött Notion automatizmus screenshot alapján) és a chat-szerű kommentek."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Contact
from app.models.deliverable import Deliverable
from app.models.deliverable_comment import DeliverableComment
from app.models.employee import Employee
from app.models.feedback import Feedback
from app.models.rate import Rate
from app.models.timesheet import Timesheet
from app.models.user_access import PageAccessConfig
from app.schemas.deliverable_actions import (
    AssignableEmployee,
    CommentRead,
    ContactOption,
    TimerEmployeeSummary,
    TimerState,
    VinyoOptions,
)
from app.services import notifications

UTOMUNKA_PAGE = "/utomunka"


def list_assignable_employees(db: Session) -> list[AssignableEmployee]:
    """Kik választhatók az "Assigned To" mezőbe - csak azok, akiknek van
    jelszavuk (be tudnak lépni) ÉS akiknek nincs korlátozva a hozzáférése az
    /utomunka oldaltól (nincs PageAccessConfig soruk, vagy allowed_pages=null,
    vagy tartalmazza az /utomunka-t)."""
    configs = {c.employee_id: c.allowed_pages for c in db.scalars(select(PageAccessConfig))}
    employees = db.scalars(select(Employee).where(Employee.hashed_password.is_not(None), Employee.is_active.is_(True)))
    result = []
    for e in employees:
        allowed_pages = configs.get(e.id)
        if e.id not in configs or allowed_pages is None or UTOMUNKA_PAGE in allowed_pages:
            result.append(AssignableEmployee(id=e.id, full_name=e.full_name))
    return sorted(result, key=lambda e: e.full_name)


def get_vinyo_options(db: Session) -> VinyoOptions:
    """Az eddig valaha használt vinyó-értékek egyesített, duplikátum-mentes
    listája (lásd Deliverable.vinyok JSON lista) - a frontend ebből épít
    választható (checkbox-listás) legördülőt, új érték szabadon hozzáadható."""
    seen: dict[str, None] = {}
    for (raw,) in db.execute(select(Deliverable.vinyok).where(Deliverable.vinyok.is_not(None))):
        if isinstance(raw, list):
            for v in raw:
                if isinstance(v, str) and v not in seen:
                    seen[v] = None
    return VinyoOptions(options=sorted(seen.keys()))


def _recompute_email_list(deliverable: Deliverable) -> None:
    emails = [c.email for c in deliverable.megrendeloi_kontaktok if c.email]
    deliverable.megrendeloi_email_cimek = ", ".join(emails) if emails else None


def set_contacts(db: Session, deliverable: Deliverable, contact_ids: list[int]) -> Deliverable:
    """A "Megrendelői kontaktok" relációt cseréli le a megadott kontakt-ID-kre,
    és újraszámolja a megrendeloi_email_cimek formula-mezőt (vesszővel
    elválasztott email-lista) - ez utóbbi sosem szerkeszthető közvetlenül."""
    contacts = db.scalars(select(Contact).where(Contact.id.in_(contact_ids))).all() if contact_ids else []
    deliverable.megrendeloi_kontaktok = list(contacts)
    _recompute_email_list(deliverable)
    db.commit()
    db.refresh(deliverable)
    return deliverable


def list_contacts(deliverable: Deliverable) -> list[ContactOption]:
    return [ContactOption(id=c.id, full_name=c.full_name, email=c.email) for c in deliverable.megrendeloi_kontaktok]


def start_timer(db: Session, deliverable: Deliverable, current_user: Employee) -> None:
    """"Start" gomb - új, nyitott (end_date=None) Timesheet sort hoz létre a
    bejelentkezett felhasználóhoz - egyszerre csak egy fusson, különben a
    Stop nem tudná egyértelműen eldönteni, melyiket zárja le."""
    open_row = db.scalar(
        select(Timesheet).where(
            Timesheet.deliverable_id == deliverable.id,
            Timesheet.employee_id == current_user.id,
            Timesheet.end_date.is_(None),
        )
    )
    if open_row is not None:
        raise ValueError("Már fut egy időmérés ehhez az anyaghoz - előbb állítsd le.")

    rate = db.scalar(select(Rate).where(Rate.employee_id == current_user.id))
    db.add(
        Timesheet(
            employee_id=current_user.id,
            deliverable_id=deliverable.id,
            start_date=datetime.now(timezone.utc),
            akkori_orabere=rate.orabler if rate else None,
        )
    )
    db.commit()


def stop_timer(db: Session, deliverable: Deliverable, current_user: Employee) -> None:
    """"Stop" gomb - lezárja a nyitott Timesheet sort, kiszámolja a ledolgozott
    percet és (ha van óradíj) a költséget."""
    open_row = db.scalar(
        select(Timesheet).where(
            Timesheet.deliverable_id == deliverable.id,
            Timesheet.employee_id == current_user.id,
            Timesheet.end_date.is_(None),
        )
    )
    if open_row is None:
        raise ValueError("Nincs futó időmérés ehhez az anyaghoz.")

    open_row.end_date = datetime.now(timezone.utc)
    minutes = open_row.idotartam_perc or 0
    open_row.time_minutes = minutes
    if open_row.akkori_orabere:
        open_row.koltseg = round((minutes / 60) * float(open_row.akkori_orabere), 2)
    db.commit()


def get_timer_state(db: Session, deliverable: Deliverable, current_user: Employee) -> TimerState:
    rows = db.scalars(select(Timesheet).where(Timesheet.deliverable_id == deliverable.id)).all()

    my_running_since = None
    by_employee_minutes: dict[int, float] = {}
    by_employee_cost: dict[int, float] = {}
    for row in rows:
        if row.employee_id == current_user.id and row.end_date is None and row.start_date is not None:
            my_running_since = row.start_date
        if row.end_date is not None and row.start_date is not None:
            minutes = row.time_minutes if row.time_minutes is not None else row.idotartam_perc or 0
            by_employee_minutes[row.employee_id] = by_employee_minutes.get(row.employee_id, 0) + float(minutes)
            if row.koltseg is not None:
                by_employee_cost[row.employee_id] = by_employee_cost.get(row.employee_id, 0) + float(row.koltseg)

    employee_ids = list(by_employee_minutes.keys())
    names = {e.id: e.full_name for e in db.scalars(select(Employee).where(Employee.id.in_(employee_ids)))} if employee_ids else {}

    by_employee = [
        TimerEmployeeSummary(
            employee_id=eid,
            full_name=names.get(eid, "Ismeretlen"),
            total_minutes=minutes,
            total_cost=by_employee_cost.get(eid),
        )
        for eid, minutes in by_employee_minutes.items()
    ]
    total_minutes = sum(by_employee_minutes.values())
    total_cost = sum(by_employee_cost.values()) if by_employee_cost else None

    return TimerState(my_running_since=my_running_since, by_employee=by_employee, total_minutes=total_minutes, total_cost=total_cost)


def send_visszajelzes(db: Session, deliverable: Deliverable, current_user: Employee) -> Feedback:
    """"Visszajelzés küldése" gomb - a csatolt Notion automatizmus portolása:
    új Feedback sort hoz létre a jelenlegi értékelés-mezőkből, majd
    visszaállítja (kiüríti) azokat az anyagon, hogy a következő körhöz újra
    kitölthetők legyenek."""
    feedback = Feedback(
        deliverable_id=deliverable.id,
        project_id=deliverable.project_id,
        visszajelzo_employee_id=current_user.id,
        technikai_helyesseg=deliverable.technikai_helyesseg,
        kreativ_kepivilag=deliverable.kreativ_es_kepi_vilag,
        nyersanyag_felhasznalhatosaga=deliverable.nyersanyag_felhasznalhatosaga,
        visszajelzes_szoveg=deliverable.egyeb_megjegyzes,
    )
    db.add(feedback)

    deliverable.technikai_helyesseg = None
    deliverable.kreativ_es_kepi_vilag = None
    deliverable.nyersanyag_felhasznalhatosaga = None
    deliverable.egyeb_megjegyzes = None

    db.commit()
    db.refresh(feedback)
    return feedback


def list_comments(db: Session, deliverable_id: int) -> list[CommentRead]:
    rows = db.scalars(
        select(DeliverableComment)
        .where(DeliverableComment.deliverable_id == deliverable_id)
        .order_by(DeliverableComment.created_at)
    ).all()
    return [
        CommentRead(
            id=c.id,
            deliverable_id=c.deliverable_id,
            employee_id=c.employee_id,
            employee_name=c.employee.full_name,
            body=c.body,
            created_at=c.created_at,
        )
        for c in rows
    ]


def add_comment(db: Session, deliverable_id: int, current_user: Employee, body: str) -> CommentRead:
    comment = DeliverableComment(deliverable_id=deliverable_id, employee_id=current_user.id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    deliverable = db.get(Deliverable, deliverable_id)
    title = deliverable.projekt_neve or f"Anyag #{deliverable.id}"
    already_notified: set[int] = set()

    for employee_id in notifications.extract_mentioned_employee_ids(body, db):
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="mention",
            message=f"{current_user.full_name} megemlített egy hozzászólásban: {title}",
            link=f"{UTOMUNKA_PAGE}/{deliverable.id}",
            actor_id=current_user.id,
        )
        already_notified.add(employee_id)

    for employee_id in filter(None, [deliverable.assigned_to_employee_id, deliverable.aki_felvezette_employee_id]):
        if employee_id in already_notified:
            continue
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="comment",
            message=f"{current_user.full_name} kommentelt: {title}",
            link=f"{UTOMUNKA_PAGE}/{deliverable.id}",
            actor_id=current_user.id,
        )
        already_notified.add(employee_id)

    db.commit()
    return CommentRead(
        id=comment.id,
        deliverable_id=comment.deliverable_id,
        employee_id=comment.employee_id,
        employee_name=current_user.full_name,
        body=comment.body,
        created_at=comment.created_at,
    )
