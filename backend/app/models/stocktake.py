from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class StocktakeSession(TimestampMixin, Base):
    """Egy leltározási esemény - a "Leltározás" gombbal indítható, a felvett
    Equipment-ek pillanatnyi állapotát nézi végig valaki (lásd StocktakeItem),
    a régi, dátumonként külön oszlopként tárolt leltar_2024xxxx mezők helyett
    általánosított, ismételhető formában."""

    __tablename__ = "stocktake_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column()

    started_by: Mapped["Employee"] = relationship()
    items: Mapped[list["StocktakeItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="StocktakeItem.id"
    )

    @property
    def started_by_name(self) -> str:
        return self.started_by.full_name


class StocktakeItem(TimestampMixin, Base):
    """Egy eszköz sora egy leltározási eseményben - "asset" eszközöknél a
    státuszát (lásd Equipment.allapot opciói) állítja be az auditáló, "stock"
    eszközöknél a ténylegesen megszámolt darabszámot rögzíti az elvárt
    (Equipment.osszes_mennyiseg) mennyiséghez képest. Mindkét mező módosítása
    azonnal visszaírja a kapcsolódó Equipment rekordot is (lásd
    services/stocktake.py update_item), hogy a leltár valós adatot hagyjon
    maga után, nem csak egy elkülönült auditnaplót."""

    __tablename__ = "stocktake_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("stocktake_sessions.id"), nullable=False)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)

    expected_qty: Mapped[int | None] = mapped_column(Integer, comment="Equipment.osszes_mennyiseg pillanatfelvétele a leltár indításakor")
    counted_qty: Mapped[int | None] = mapped_column(Integer, comment="A leltározás során ténylegesen megszámolt darabszám")
    status: Mapped[str | None] = mapped_column(String(50), comment="A leltározás során beállított állapot (lásd Equipment.allapot)")

    session: Mapped["StocktakeSession"] = relationship(back_populates="items")
    equipment: Mapped["Equipment"] = relationship()

    @property
    def equipment_nev(self) -> str:
        return self.equipment.nev

    @property
    def kategoria(self) -> str | None:
        return self.equipment.kategoria

    @property
    def track_mode(self) -> str:
        return self.equipment.track_mode.value
