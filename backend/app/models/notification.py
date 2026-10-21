from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Notification(TimestampMixin, Base):
    """Egy értesítés egy munkatársnak - hozzászólásban taggelve lett, vagy
    kapott/kiosztottak neki valamit (pl. Utómunka Assigned To, Feladat
    felelős) - lásd services/notifications.py."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str] = mapped_column(String(300), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employee: Mapped["Employee"] = relationship()
