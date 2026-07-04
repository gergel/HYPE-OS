from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class FieldVisibilityConfig(Base):
    """Melyik mezők jelenjenek meg egy adott entitástípus részletnézetén - a
    Beállítások oldalon admin által szerkeszthető, mindenkire egyformán
    vonatkozó lista. entity_type az ENTITY_PATHS frontend kulcsokkal egyezik
    (pl. "project", "employee"). visible_fields=None (nincs config sor) vagy
    üres lista -> nincs szűrés, minden mező látszik (alapértelmezett viselkedés)."""

    __tablename__ = "field_visibility_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    visible_fields: Mapped[list[str] | None] = mapped_column(JSON)
