from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Folder(TimestampMixin, Base):
    """Média mappa egy Project alatt."""

    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="folders")
    media_items: Mapped[list["Media"]] = relationship(back_populates="folder")


class Media(TimestampMixin, Base):
    """Feltöltött videó/kép - Cloudflare R2 storage_key alapján (Storage modul)."""

    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"))

    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="R2/S3 kulcs")
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    resolution_label: Mapped[str | None] = mapped_column(String(20))
    # 64 bites: egyetlen videó master is lehet 2 GiB felett (a korábbi 32 bites
    # INTEGER 2 147 483 647 bájt felett "integer out of range" hibát adott).
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    #: A forrásobjektum tartalmi hash-e (hex sha256), ha ismert. Az export
    #: ujjlenyomatába beleszámít, így a tartalom változása új exportot kényszerít.
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="processing", comment="processing/ready/failed")

    project: Mapped["Project"] = relationship(back_populates="media_items")
    folder: Mapped["Folder"] = relationship(back_populates="media_items")
