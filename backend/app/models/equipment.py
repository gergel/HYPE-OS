from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.project import project_equipment


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

    # a 'Leltár' Notion tábla maradék mezői, egyenként (lásd scripts/dump_extra_keys.py)
    leltar_20240415: Mapped[bool | None] = mapped_column(Boolean, comment="2024.04.15. Leltár")
    leltar_20250104: Mapped[bool | None] = mapped_column(Boolean, comment="2025.01.04. Leltár")
    hasznalhato: Mapped[str | None] = mapped_column(String(50), comment="Használható?")
    leltar_20240526: Mapped[bool | None] = mapped_column(Boolean, comment="2024.05.26. Leltár")
    rendszerbe_kerules_idopontja: Mapped[datetime | None] = mapped_column(DateTime)
    letrehozta_notion: Mapped[dict | list | None] = mapped_column(JSON, comment="Created by")
    leltar_20240620: Mapped[bool | None] = mapped_column(Boolean, comment="2024.06.20. Leltár")
    hany_napot_dolgozott: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status_notion: Mapped[str | None] = mapped_column(String(50), comment="status")
    hany_forgatason_vett_reszt: Mapped[str | None] = mapped_column(String(50))
    mai_notion: Mapped[bool | None] = mapped_column(Boolean, comment="mai")
    leltar_20250519: Mapped[bool | None] = mapped_column(Boolean, comment="2025.05.19. - Leltár")
    qr_kod: Mapped[str | None] = mapped_column(String(255), comment="QR kód")
    created_at_notion: Mapped[datetime | None] = mapped_column(DateTime, comment="Created time")
    leltar_tetelek_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Leltár tételek")
    forgatasi_napok: Mapped[str | None] = mapped_column(Text, comment="Forgatási napok")
    projektek_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Projektek")
    qr: Mapped[str | None] = mapped_column(String(50))
    eszkozkiviteli_ki_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="eszközkiviteli ki")
    eszkozkiviteli_vissza_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="eszközkiviteli vissza")
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    stock_qty: Mapped[float | None] = mapped_column(Numeric(12, 2))
    zoom_atfogas: Mapped[dict | list | None] = mapped_column(JSON, comment="Zoom átfogás")
    stock_igenyek_notion_ids: Mapped[dict | list | None] = mapped_column(JSON, comment="Stock igények")
    jovobeni: Mapped[str | None] = mapped_column(Text, comment="JÖVŐBENI")
    megeri_e_szerelni: Mapped[str | None] = mapped_column(String(50), comment="Megéri e szerelni")
    szerviz_leiras: Mapped[str | None] = mapped_column(Text, comment="Szervíz leírás")
    selejtezes_elhagyas_datuma: Mapped[date | None] = mapped_column(Date, comment="Selejtezés /elhagyás dátuma")
    ahol_utoljara_volt: Mapped[str | None] = mapped_column(Text, comment="Ahol utoljára volt")

    assignments: Mapped[list["Assignment"]] = relationship(back_populates="equipment")
    projects: Mapped[list["Project"]] = relationship(secondary=project_equipment, back_populates="equipment")

    @property
    def project_ids(self) -> list[int]:
        """Melyik projekteken volt kint ez az eszköz - a Project importere tölti fel
        a 'Kivitt eszközök'/'Visszahozott eszközök' Notion relation-ök feloldásával."""
        return [p.id for p in self.projects]


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
