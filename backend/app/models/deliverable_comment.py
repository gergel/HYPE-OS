from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DeliverableComment(TimestampMixin, Base):
    """Egy hozzászólás egy Utómunka (Deliverable) oldal alján lévő chat-ben -
    a résztvevők névvel beszélgetnek és @Név formában tudnak taggelni egymást
    (lásd frontend components/deliverable/CommentsSection.tsx)."""

    __tablename__ = "deliverable_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    deliverable_id: Mapped[int] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    deliverable: Mapped["Deliverable"] = relationship(back_populates="comments")
    employee: Mapped["Employee"] = relationship()
