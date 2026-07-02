from datetime import date
from enum import StrEnum

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
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
    """Ügyfél-nézet - jelszó/share link alapú videó-portál (/p/{slug})."""

    __tablename__ = "portals"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True, nullable=False)

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
    expires_at: Mapped[date | None] = mapped_column(Date)

    project: Mapped["Project"] = relationship(back_populates="portal")
    payment: Mapped["Payment"] = relationship(back_populates="portal", uselist=False)


class Payment(TimestampMixin, Base):
    """Opcionális Barion fizetés a Portálon keresztül."""

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

    portal: Mapped["Portal"] = relationship(back_populates="payment")
    revenue: Mapped["Revenue"] = relationship(back_populates="payments")
