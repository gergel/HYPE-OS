"""Leltározás (Stocktake) - a "Leltározás" gomb egy új StocktakeSession-t indít,
ami minden felvett Equipment-hez felvesz egy sort (a jelenlegi állapot/mennyiség
pillanatfelvételével), amiket az auditáló végignéz és frissít. A régi,
dátumonként külön oszlopban tárolt leltar_2024xxxx Notion-mezők helyett ez egy
általánosított, ismételhető, valódi táblás megoldás."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.equipment import Equipment
from app.models.employee import Employee
from app.models.stocktake import StocktakeItem, StocktakeSession
from app.schemas.stocktake import (
    StocktakeItemUpdate,
    StocktakeMissingStock,
    StocktakeStatusGroup,
    StocktakeStatusGroupItem,
    StocktakeSummary,
    StocktakeSurplusStock,
)

HEALTHY_STATUSES = {"Jó", "Szerelve"}

# Ezekhez a státuszokhoz MAGYARÁZAT is kell, mielőtt a leltár lezárható lenne
# (lásd hianyzo_magyarazatok / complete_session). Egy hónappal később a puszta
# "Szervíz" vagy "Szerelendő" állapotból már senki nem tudja, mi a baja a
# gépnek, hol van, és ki vitte el - a leltár épp az a pillanat, amikor ezt
# valaki még fejből tudja.
#
# A többi nem-"Jó" státusz (Selejt, Elhagyva) szándékosan nincs itt: azoknál
# maga a szó megmondja, mi történt.
MAGYARAZATOT_IGENYLO_STATUSZOK = {"Szerelendő", "Szervíz"}


def start_session(db: Session, current_user: Employee) -> StocktakeSession:
    session = StocktakeSession(started_by_employee_id=current_user.id)
    db.add(session)
    db.flush()

    for equipment in db.scalars(select(Equipment)):
        db.add(
            StocktakeItem(
                session_id=session.id,
                equipment_id=equipment.id,
                # A track_mode Notion-import-eredetű, sok esetben pontatlan
                # besorolás - az elvárt mennyiséget attól függetlenül vesszük
                # át, hogy az Equipment.osszes_mennyiseg ténylegesen ki van-e
                # töltve, nem csak "stock" track_mode-nál.
                expected_qty=equipment.osszes_mennyiseg,
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
    if item.session.completed_at is not None:
        raise ValueError("Ez a leltározás már le van zárva, nem módosítható.")
    if payload.status is not None:
        item.status = payload.status
        item.equipment.allapot = payload.status
    if payload.counted_qty is not None:
        item.counted_qty = payload.counted_qty
        item.equipment.osszes_mennyiseg = payload.counted_qty
    if payload.megjegyzes is not None:
        # Üres szöveg = nincs magyarázat (a lezárás így számon is kéri).
        item.megjegyzes = payload.megjegyzes.strip() or None
    db.commit()
    db.refresh(item)
    return item


def hianyzo_magyarazatok(session: StocktakeSession) -> list[StocktakeItem]:
    """Azok a tételek, amiknek a státusza magyarázatot igényel, de nincs
    hozzáírva semmi (lásd MAGYARAZATOT_IGENYLO_STATUSZOK)."""
    return [
        item
        for item in session.items
        if item.status in MAGYARAZATOT_IGENYLO_STATUSZOK and not (item.megjegyzes or "").strip()
    ]


class LezarasHiba(ValueError):
    """A leltár nem zárható le - a felület ezt az üzenetet mutatja."""


def complete_session(db: Session, session: StocktakeSession) -> StocktakeSession:
    hianyzo = hianyzo_magyarazatok(session)
    if hianyzo:
        nevek = ", ".join(f"{i.equipment.nev} ({i.status})" for i in hianyzo[:10])
        tobbi = f" és még {len(hianyzo) - 10} eszköz" if len(hianyzo) > 10 else ""
        raise LezarasHiba(
            f"Előbb írd meg, miért szerelendő / miért van szervizben: {nevek}{tobbi}. "
            "Enélkül egy hónap múlva már senki nem tudja, mi a baja és hol van."
        )
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session: StocktakeSession) -> None:
    """A leltározás törlése - a tételeivel együtt (cascade).

    A leltár közben megváltoztatott Equipment-eket NEM állítjuk vissza: azok
    a valós állapotot tükrözik ("ez a gép tényleg szervizben van"), és a
    leltár törlése nem teszi vissza a kamerát a polcra. Ez a művelet a téves
    vagy duplán elindított leltárak takarítására van, nem visszavonásra."""
    db.delete(session)
    db.commit()


def get_summary(db: Session, session: StocktakeSession) -> StocktakeSummary:
    by_status: dict[str, list[StocktakeStatusGroupItem]] = {}
    missing_stock: list[StocktakeMissingStock] = []
    surplus_stock: list[StocktakeSurplusStock] = []

    for item in session.items:
        equipment = item.equipment
        if item.status and item.status not in HEALTHY_STATUSES:
            by_status.setdefault(item.status, []).append(
                StocktakeStatusGroupItem(
                    equipment_id=equipment.id,
                    nev=equipment.nev,
                    megjegyzes=item.megjegyzes,
                    magyarazat_kell=item.status in MAGYARAZATOT_IGENYLO_STATUSZOK,
                )
            )
        if item.expected_qty is not None and item.counted_qty is not None:
            if item.counted_qty < item.expected_qty:
                missing_stock.append(
                    StocktakeMissingStock(
                        equipment_id=equipment.id,
                        nev=equipment.nev,
                        expected_qty=item.expected_qty,
                        counted_qty=item.counted_qty,
                        hiany=item.expected_qty - item.counted_qty,
                    )
                )
            elif item.counted_qty > item.expected_qty:
                # A TÖBBLET is eltérés, nem öröm: vagy rosszul volt nyilvántartva
                # a készlet, vagy egy másik tétel alá könyvelt darabok kerültek
                # elő. Ha nem írjuk ki, a nyilvántartás csendben elcsúszik.
                surplus_stock.append(
                    StocktakeSurplusStock(
                        equipment_id=equipment.id,
                        nev=equipment.nev,
                        expected_qty=item.expected_qty,
                        counted_qty=item.counted_qty,
                        tobblet=item.counted_qty - item.expected_qty,
                    )
                )

    return StocktakeSummary(
        problemas_statuszok=[StocktakeStatusGroup(status=status, items=items) for status, items in sorted(by_status.items())],
        hianyzo_keszletek=missing_stock,
        tobblet_keszletek=surplus_stock,
        magyarazatra_var=[
            StocktakeStatusGroupItem(
                equipment_id=i.equipment.id, nev=i.equipment.nev, megjegyzes=None, magyarazat_kell=True
            )
            for i in hianyzo_magyarazatok(session)
        ],
    )
