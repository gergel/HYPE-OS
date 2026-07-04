from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FieldVisibilityConfig(Base):
    """Melyik mezők jelenjenek meg egy adott munkatársnak egy adott entitástípus
    részletnézetén - egyénenként állítható (nem szerepkör szerint), admin
    szerkesztheti a Beállítások oldalon. entity_type az ENTITY_PATHS frontend
    kulcsokkal egyezik (pl. "project", "employee"). visible_fields=None
    (nincs config sor) vagy üres lista -> nincs szűrés, minden mező látszik
    (alapértelmezett viselkedés annak a munkatársnak, akihez nincs beállítás)."""

    __tablename__ = "field_visibility_configs"
    __table_args__ = (UniqueConstraint("employee_id", "entity_type", name="uq_field_visibility_employee_entity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    visible_fields: Mapped[list[str] | None] = mapped_column(JSON)
