from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PageAccessConfig(Base):
    """Melyik oldalakat (lásd frontend/lib/nav.ts href-jei, pl. "/projektek")
    láthatja egy adott munkatárs, és azokon belül mit tehet - egyénenként
    állítható, nem szerepkör szerint. page_permissions=None (nincs config sor,
    vagy a mező None) -> nincs szűkítés, minden oldalt lát és mindent tehet
    (ugyanaz az alapértelmezett viselkedés, mint a FieldVisibilityConfig-nál).

    Alak: {"/projektek": ["view", "edit", "create", "delete"], "/utomunka": ["view"]} -
    egy oldal jelenléte a kulcsok között adja a láthatóságot (a middleware és a
    Sidebar ezt nézi, lásd get_my_access "allowed_pages" derivált mezője), az
    érték lista pedig azt, mit tehet RAJTA (view mindig implicit, ha a kulcs
    szerepel - a valódi kapcsoló az edit/create/delete külön-külön)."""

    __tablename__ = "page_access_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True, nullable=False)
    page_permissions: Mapped[dict[str, list[str]] | None] = mapped_column(JSON)
