from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class AgiTodoItem(TimestampMixin, Base):
    """Az ÁGI Notion-oldal "To-Do List" táblájának sorai - önálló tábla, a
    HYPE TO-DO LIST-hez hasonlóan NEM a régi, félbehagyott Task-egyesítés
    része (lásd models/task.py, models/hype_todo.py megjegyzését)."""

    __tablename__ = "agi_todo_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    feladat: Mapped[str] = mapped_column(String(500), nullable=False)
    allapot: Mapped[str | None] = mapped_column(String(50))
    #: Melyik ügyfélhez tartozik a feladat - a Notionban egyszerű címke (nem
    #: a Client táblára mutató kapcsolat), lásd models/flora_feladat.cimke.
    ugyfel: Mapped[str | None] = mapped_column(String(255))
    hatarido: Mapped[date | None] = mapped_column(Date)
    leiras: Mapped[str | None] = mapped_column(Text)
    kovetkezo_lepes: Mapped[str | None] = mapped_column(Text)
    #: "Files & media" - ha külső link (nem Notionba feltöltött fájl), mert a
    #: valódi feltöltött fájlok a DocumentAttachment táblába kerülnek (lásd
    #: services/attachments.py, entity_type="agiTodo").
    csatolt_link: Mapped[str | None] = mapped_column(String(1000))
