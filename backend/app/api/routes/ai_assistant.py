"""AI Assistant modul (Fázis 5, hype_os_build_roadmap.md) - RAG réteg a végleges Postgres
felett, tool-calling-gal. Csak a Fázis 0-4 után van értelme (lásd termékspecifikáció 6.
fejezet), amikor már megbízható, strukturált adat van a rendszerben - itt egyelőre csak a
végleges API-alak van lefektetve.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/ai-assistant", tags=["ai-assistant"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    return AskResponse(
        answer="Az AI Assistant modul Fázis 5-ben épül (lásd hype_os_build_roadmap.md) - "
        "egyelőre nincs bekötve RAG/tool-calling réteg."
    )
