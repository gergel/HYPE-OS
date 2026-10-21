from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProjectCodeComment(TimestampMixin, Base):
    """Egy hozzászólás egy Project Code oldal alján lévő chat-ben - ugyanaz a
    minta, mint az Utómunkánál (lásd models/deliverable_comment.py és
    frontend components/projektkod/CommentsSection.tsx)."""

    __tablename__ = "project_code_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    project_code: Mapped["ProjectCode"] = relationship(back_populates="comments")
    employee: Mapped["Employee"] = relationship()
