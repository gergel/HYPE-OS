from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PageAccessConfig(Base):
    """Melyik oldalakat (lásd frontend/lib/nav.ts href-jei, pl. "/projektek")
    láthatja egy adott munkatárs - egyénenként állítható, nem szerepkör szerint.
    allowed_pages=None (nincs config sor) -> nincs szűkítés, minden oldalt lát
    (ugyanaz az alapértelmezett viselkedés, mint a FieldVisibilityConfig-nál)."""

    __tablename__ = "page_access_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True, nullable=False)
    allowed_pages: Mapped[list[str] | None] = mapped_column(JSON)
