from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class FloraKomment(TimestampMixin, Base):
    """Egy hozzászólás a FLÓRA tábla egy feladatának oldalán - ugyanaz a
    chat-szerű minta, mint az Utómunkánál és a Project Code-nál (lásd
    models/deliverable_comment.py). A Notion-importtal a kártyák Notion-beli
    kommentjei is ide kerülnek (lásd notion_import/importers_wave4.py)."""

    __tablename__ = "flora_kommentek"

    id: Mapped[int] = mapped_column(primary_key=True)
    flora_feladat_id: Mapped[int] = mapped_column(ForeignKey("flora_feladatok.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    flora_feladat: Mapped["FloraFeladat"] = relationship(back_populates="kommentek")
    employee: Mapped["Employee"] = relationship()
