"""Leltározás (Stocktake) - a "Leltározás" gomb egy új StocktakeSession-t indít,
ami minden felvett Equipment-hez felvesz egy sort (a jelenlegi állapot/mennyiség
pillanatfelvételével), amiket az auditáló végignéz és frissít. A régi,
dátumonként külön oszlopban tárolt leltar_2024xxxx Notion-mezők helyett ez egy
általánosított, ismételhető, valódi táblás megoldás."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.equipment import Equipment, TrackMode
from app.models.employee import Employee
from app.models.stocktake import StocktakeItem, StocktakeSession
from app.schemas.stocktake import (
    StocktakeItemUpdate,
    StocktakeMissingStock,
    StocktakeStatusGroup,
    StocktakeStatusGroupItem,
    StocktakeSummary,
)

HEALTHY_STATUSES = {"Jó", "Szerelve"}


def start_session(db: Session, current_user: Employee) -> StocktakeSession:
    session = StocktakeSession(started_by_employee_id=current_user.id)
    db.add(session)
    db.flush()

    for equipment in db.scalars(select(Equipment)):
        db.add(
            StocktakeItem(
                session_id=session.id,
                equipment_id=equipment.id,
                expected_qty=equipment.osszes_mennyiseg if equipment.track_mode == TrackMode.STOCK else None,
                counted_qty=None,
                status=equipment.allapot,
            )
        )
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session) -> list[StocktakeSession]:
    return db.scalars(
        select(StocktakeSession).options(joinedload(StocktakeSession.started_by)).order_by(StocktakeSession.created_at.desc())
    ).all()


def get_session(db: Session, session_id: int) -> StocktakeSession | None:
    return db.scalar(
        select(StocktakeSession)
        .where(StocktakeSession.id == session_id)
        .options(joinedload(StocktakeSession.items).joinedload(StocktakeItem.equipment), joinedload(StocktakeSession.started_by))
    )


def get_item(db: Session, session_id: int, item_id: int) -> StocktakeItem | None:
    return db.scalar(
        select(StocktakeItem).where(StocktakeItem.id == item_id, StocktakeItem.session_id == session_id)
    )


def update_item(db: Session, item: StocktakeItem, payload: StocktakeItemUpdate) -> StocktakeItem:
    """Az itemen kívül a mögötte lévő Equipment rekordot is frissíti (élő
    állapot/mennyiség), hogy a leltár valós adatot hagyjon maga után."""
    if payload.status is not None:
        item.status = payload.status
        item.equipment.allapot = payload.status
    if payload.counted_qty is not None:
        item.counted_qty = payload.counted_qty
        item.equipment.osszes_mennyiseg = payload.counted_qty
    db.commit()
    db.refresh(item)
    return item


def complete_session(db: Session, session: StocktakeSession) -> StocktakeSession:
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def get_summary(db: Session, session: StocktakeSession) -> StocktakeSummary:
    by_status: dict[str, list[StocktakeStatusGroupItem]] = {}
    missing_stock: list[StocktakeMissingStock] = []

    for item in session.items:
        equipment = item.equipment
        if item.status and item.status not in HEALTHY_STATUSES:
            by_status.setdefault(item.status, []).append(
                StocktakeStatusGroupItem(equipment_id=equipment.id, nev=equipment.nev)
            )
        if item.expected_qty is not None and item.counted_qty is not None and item.counted_qty < item.expected_qty:
            missing_stock.append(
                StocktakeMissingStock(
                    equipment_id=equipment.id,
                    nev=equipment.nev,
                    expected_qty=item.expected_qty,
                    counted_qty=item.counted_qty,
                    hiany=item.expected_qty - item.counted_qty,
                )
            )

    return StocktakeSummary(
        problemas_statuszok=[StocktakeStatusGroup(status=status, items=items) for status, items in sorted(by_status.items())],
        hianyzo_keszletek=missing_stock,
    )
