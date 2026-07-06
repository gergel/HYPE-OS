from datetime import date
from enum import StrEnum

from sqlalchemy import BigInteger, Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PortalStatus(StrEnum):
    DRAFT = "draft"
    LIVE = "live"
    ARCHIVED = "archived"


class Brand(StrEnum):
    HYPE = "hype"
    CONTENTBEE = "contentbee"


class PaymentMode(StrEnum):
    CONTACT = "contact"
    PAID = "paid"


class Portal(TimestampMixin, Base):
    """Ügyfél-nézet - jelszó/share link alapú videó-portál (/p/{slug}), 1:1 egy
    valódi Project-hez kötve (nincs kettőzött cím/ügyfélnév - lásd
    title_override/client_name_override, amik None esetén a Project saját
    mezőire esnek vissza, lásd services/portal_storage.py resolve_* helperek).
    A tényleges videó/kép feltöltést és FFmpeg HLS-transzkódolást a
    Hype-repo-main (különálló client-portál projekt) 1:1 portolt pipeline-ja
    végzi (lásd services/portal_storage.py, portal_transcode.py, workers/portal_tasks.py)."""

    __tablename__ = "portals"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True, nullable=False)

    title_override: Mapped[str | None] = mapped_column(String(255))
    client_name_override: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    project_date_override: Mapped[str | None] = mapped_column(String(100))

    password_hash: Mapped[str | None] = mapped_column(String(255))
    share_token: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[PortalStatus] = mapped_column(
        Enum(PortalStatus, name="portal_status", values_callable=lambda obj: [e.value for e in obj]),
        default=PortalStatus.DRAFT,
        nullable=False,
    )
    brand: Mapped[Brand] = mapped_column(
        Enum(Brand, name="portal_brand", values_callable=lambda obj: [e.value for e in obj]),
        default=Brand.HYPE,
        nullable=False,
    )
    payment_mode: Mapped[PaymentMode] = mapped_column(
        Enum(PaymentMode, name="portal_payment_mode", values_callable=lambda obj: [e.value for e in obj]),
        default=PaymentMode.CONTACT,
        nullable=False,
    )
    expires_at: Mapped[date | None] = mapped_column(Date)
    notion_page_id: Mapped[str | None] = mapped_column(String(255), index=True)

    project: Mapped["Project"] = relationship(back_populates="portal")
    payments: Mapped[list["Payment"]] = relationship(back_populates="portal")
    folders: Mapped[list["PortalFolder"]] = relationship(
        back_populates="portal", cascade="all, delete-orphan", order_by="PortalFolder.sort_order"
    )
    videos: Mapped[list["PortalVideo"]] = relationship(
        back_populates="portal", cascade="all, delete-orphan", order_by="PortalVideo.sort_order"
    )
    images: Mapped[list["PortalImage"]] = relationship(
        back_populates="portal", cascade="all, delete-orphan", order_by="PortalImage.sort_order"
    )


class Payment(TimestampMixin, Base):
    """Opcionális Barion fizetés a Portálon keresztül - egy Portalnak több
    Payment rekordja is lehet az idők során (minden hosszabbítás egy új sor)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_request_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    portal_id: Mapped[int | None] = mapped_column(ForeignKey("portals.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    revenue_id: Mapped[int | None] = mapped_column(ForeignKey("revenues.id"))

    osszeg_huf: Mapped[float | None] = mapped_column(Numeric(12, 2))
    mode: Mapped[PaymentMode] = mapped_column(
        Enum(PaymentMode, name="payment_mode", values_callable=lambda obj: [e.value for e in obj]),
        default=PaymentMode.CONTACT,
        nullable=False,
    )
    allapot: Mapped[str | None] = mapped_column(String(50))
    barion_payment_id: Mapped[str | None] = mapped_column(String(255))

    portal: Mapped["Portal"] = relationship(back_populates="payments")
    revenue: Mapped["Revenue"] = relationship(back_populates="payments")


class PortalFolder(TimestampMixin, Base):
    """Videó/kép-csoportosító mappa egy Portálon belül (pl. "Werkfilm", "Fotók")."""

    __tablename__ = "portal_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    portal: Mapped["Portal"] = relationship(back_populates="folders")
    videos: Mapped[list["PortalVideo"]] = relationship(back_populates="folder", order_by="PortalVideo.sort_order")
    images: Mapped[list["PortalImage"]] = relationship(back_populates="folder", order_by="PortalImage.sort_order")


class PortalVideo(TimestampMixin, Base):
    """Feltöltött videó egy Portálon - R2-be feltöltött eredeti MP4 + a Celery
    worker (workers/portal_tasks.py) által generált HLS + thumbnail."""

    __tablename__ = "portal_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("portal_folders.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    source_key: Mapped[str | None] = mapped_column(String(500), comment="Eredeti mp4 R2 kulcsa")
    mp4_url: Mapped[str | None] = mapped_column(String(500))
    hls_url: Mapped[str | None] = mapped_column(String(500), comment=".m3u8 master playlist URL")
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))

    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    resolution_label: Mapped[str | None] = mapped_column(String(20))
    aspect_ratio_label: Mapped[str | None] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="processing", comment="uploading/processing/ready/failed")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    portal: Mapped["Portal"] = relationship(back_populates="videos")
    folder: Mapped["PortalFolder"] = relationship(back_populates="videos")


class PortalImage(TimestampMixin, Base):
    """Feltöltött fotó egy Portálon (R2-be feltöltve, automata JPEG thumbnail-lel)."""

    __tablename__ = "portal_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("portal_folders.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    key: Mapped[str | None] = mapped_column(String(500), comment="Eredeti kép R2 kulcsa")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    portal: Mapped["Portal"] = relationship(back_populates="images")
    folder: Mapped["PortalFolder"] = relationship(back_populates="images")
