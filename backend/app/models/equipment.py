from datetime import date
from enum import StrEnum

from sqlalchemy import JSON, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class TrackMode(StrEnum):
    """asset = egyedi eszköz (pl. 1 db kamera), stock = darabszám-alapú (pl. HDMI kábel)."""

    ASSET = "asset"
    STOCK = "stock"


class Equipment(TimestampMixin, Base):
    """Felszerelés - Leltár + Leltárak + Leltár tételek + Archive technika egyesítve."""

    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(120), unique=True)
    kategoria: Mapped[str | None] = mapped_column(String(100))
    allapot: Mapped[str | None] = mapped_column(String(50))
    archive_statusz: Mapped[str | None] = mapped_column(String(50))
    track_mode: Mapped[TrackMode] = mapped_column(
        Enum(TrackMode, name="equipment_track_mode", values_callable=lambda obj: [e.value for e in obj]),
        default=TrackMode.ASSET,
        nullable=False,
    )
    osszes_mennyiseg: Mapped[int | None] = mapped_column(Integer, comment="csak stock track_mode esetén relevans")
    extra: Mapped[dict | None] = mapped_column(JSON)

    assignments: Mapped[list["Assignment"]] = relationship(back_populates="equipment")


class Assignment(TimestampMixin, Base):
    """Eszköz kivitel/visszahozás - egy Project-hez rendelt Equipment (ütközés-detektálás alapja)."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)

    qty: Mapped[int] = mapped_column(Integer, default=1, comment="stock track_mode esetén hány db")
    aki_kivitte: Mapped[str | None] = mapped_column(String(255))
    kivitel_datuma: Mapped[date | None] = mapped_column(Date)
    aki_visszahozta: Mapped[str | None] = mapped_column(String(255))
    visszahozatal_datuma: Mapped[date | None] = mapped_column(Date)
    extra: Mapped[dict | None] = mapped_column(JSON)

    equipment: Mapped["Equipment"] = relationship(back_populates="assignments")
    project: Mapped["Project"] = relationship(back_populates="assignments")
