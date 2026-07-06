from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee
from app.schemas.stocktake import (
    StocktakeItemRead,
    StocktakeItemUpdate,
    StocktakeSessionListItem,
    StocktakeSessionRead,
    StocktakeSummary,
)
from app.services import stocktake

router = APIRouter(prefix="/stocktake", tags=["stocktake"])


def _get_session_or_404(session_id: int, db: Session):
    session = stocktake.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leltározás nem található")
    return session


@router.post("/sessions", response_model=StocktakeSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(db: Session = Depends(get_db), current_user: Employee = Depends(require_page_action("/felszereles", "create"))):
    session = stocktake.start_session(db, current_user)
    return stocktake.get_session(db, session.id)


@router.get("/sessions", response_model=list[StocktakeSessionListItem])
def list_sessions(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    sessions = stocktake.list_sessions(db)
    return [
        StocktakeSessionListItem(
            id=s.id, started_by_name=s.started_by_name, created_at=s.created_at, completed_at=s.completed_at, item_count=len(s.items)
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=StocktakeSessionRead)
def get_session(session_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    return _get_session_or_404(session_id, db)


@router.patch("/sessions/{session_id}/items/{item_id}", response_model=StocktakeItemRead)
def update_item(
    session_id: int,
    item_id: int,
    payload: StocktakeItemUpdate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action("/felszereles", "edit")),
):
    item = stocktake.get_item(db, session_id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leltár-tétel nem található")
    try:
        return stocktake.update_item(db, item, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/complete", response_model=StocktakeSessionRead)
def complete_session(
    session_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action("/felszereles", "edit"))
):
    session = _get_session_or_404(session_id, db)
    stocktake.complete_session(db, session)
    return stocktake.get_session(db, session_id)


@router.get("/sessions/{session_id}/summary", response_model=StocktakeSummary)
def get_summary(session_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    session = _get_session_or_404(session_id, db)
    return stocktake.get_summary(db, session)
