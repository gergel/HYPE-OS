from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class HypeTodoKomment(TimestampMixin, Base):
    """Egy hozzászólás a HYPE TO-DO LIST egy feladatának oldalán - ugyanaz a
    chat-szerű minta, mint az Utómunkánál és a FLÓRA táblánál (lásd
    models/flora_komment.py). A Notion-import a feladatok Notion-beli
    kommentjeit is ide hozza (lásd notion_import/importers_wave4.py)."""

    __tablename__ = "hype_todo_kommentek"

    id: Mapped[int] = mapped_column(primary_key=True)
    hype_todo_id: Mapped[int] = mapped_column(ForeignKey("hype_todo_items.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    hype_todo: Mapped["HypeTodoItem"] = relationship(back_populates="kommentek")
    employee: Mapped["Employee"] = relationship()
