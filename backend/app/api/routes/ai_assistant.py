"""AI Assistant - Anthropic Claude tool-calling a végleges Postgres felett (lásd
app/services/ai_assistant.py). A tényleges adathozzáférés a bejelentkezett
felhasználó saját page_permissions/field_visibility jogosultsága szerint
szűrve történik - lásd a service modul docstringjét a részletekért."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee
from app.services import ai_assistant

router = APIRouter(prefix="/ai-assistant", tags=["ai-assistant"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    return AskResponse(answer=ai_assistant.ask(db, current_user, payload.question))
