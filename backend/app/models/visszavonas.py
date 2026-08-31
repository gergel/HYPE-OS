"""Törölt rekordok pillanatképei a Ctrl+Z-hez.

A felhasználó kérése: a véletlen törlést vissza lehessen hozni. A generikus
törlés (crud_router delete) törlés ELŐTT ide menti a rekord összes sima
oszlopát, a visszaállító végpont (routes/visszavonas.py) pedig ebből teszi
vissza a sort - UGYANAZZAL az id-vel, így a rá mutató, még élő hivatkozások
is helyreállnak. A kapcsolt sorok (pl. kaszkáddal törölt gyerek-rekordok)
nem részei a pillanatképnek - ez a "gyors visszavonás", nem teljes mentés.
"""

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ToroltRekord(TimestampMixin, Base):
    __tablename__ = "torolt_rekordok"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A modell __tablename__-je - ebből találja meg a visszaállítás a táblát.
    tabla: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rekord_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: {oszlopnév: JSON-békévé alakított érték} - dátumok ISO-szövegként.
    adatok: Mapped[dict] = mapped_column(JSON, nullable=False)
    #: Ki törölte - csak ő (vagy admin) állíthatja vissza.
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), index=True)
    #: Igaz, ha már visszaállították - kétszer nem lehet.
    visszaallitva: Mapped[bool] = mapped_column(default=False, nullable=False)
