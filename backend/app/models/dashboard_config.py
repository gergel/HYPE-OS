from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DashboardConfig(Base):
    """Melyik widgetek (lásd frontend widget-kulcsok, pl. "mai_feladatok")
    jelenjenek meg egy adott munkatárs Dashboard oldalán - önkiszolgáló, bárki
    csak a sajátját szerkesztheti (nincs admin-kapcsolat, tisztán megjelenítési
    preferencia). visible_widgets=None (nincs config sor) -> minden widget látszik."""

    __tablename__ = "dashboard_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True, nullable=False)
    visible_widgets: Mapped[list[str] | None] = mapped_column(JSON)
