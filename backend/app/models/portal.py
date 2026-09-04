from datetime import date
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Text
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
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), unique=True, nullable=True)
    # Az Utómunkából ("Portál létrehozása" gomb egy Deliverable-ön) létrehozott
    # Portálok a mögöttes Projekttől függetlenül, közvetlenül egy konkrét
    # Deliverable-hoz vannak kötve - enélkül egy Projekt több Deliverable-je
    # (pl. több vágási verzió) nem kaphatna külön-külön Portált, mert a
    # project_id fenti unique kényszere csak egyet engedne projektenként.
    deliverable_id: Mapped[int | None] = mapped_column(ForeignKey("deliverables.id"), unique=True, nullable=True)

    title_override: Mapped[str | None] = mapped_column(String(255))
    client_name_override: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    project_date_override: Mapped[str | None] = mapped_column(String(100))

    password_hash: Mapped[str | None] = mapped_column(String(255))
    share_token: Mapped[str | None] = mapped_column(String(255), unique=True)
    #: FELTÖLTŐ link (a felhasználó kérése): aki ezt a tokent kapja, mappát
    #: hozhat létre és feltölthet a portálra (vagy csak a megadott mappájába),
    #: de NEM törölhet és nem lát admin-felületet - lásd
    #: routes/portal_public.py "feltoltes" végpontjai.
    feltolto_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    feltolto_folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("portal_folders.id", ondelete="SET NULL"), nullable=True
    )
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

    project: Mapped["Project | None"] = relationship(back_populates="portal")
    deliverable: Mapped["Deliverable | None"] = relationship(back_populates="portal")
    payments: Mapped[list["Payment"]] = relationship(back_populates="portal")
    # foreign_keys nélkül a feltolto_folder_id (lásd fent) kétértelművé tenné
    # a kapcsolatot - a mappák a SAJÁT portal_id-jükön lógnak.
    folders: Mapped[list["PortalFolder"]] = relationship(
        back_populates="portal",
        cascade="all, delete-orphan",
        order_by="PortalFolder.sort_order",
        foreign_keys="PortalFolder.portal_id",
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
    allapot: Mapped[str | None] = mapped_column(String(50), comment="started | succeeded | failed")
    barion_payment_id: Mapped[str | None] = mapped_column(String(255))
    #: Melyik hosszabbítás-csomagot vette (lásd routes/portal_public.py PACKAGES) -
    #: ebből tudja a visszahívás, hány nappal hosszabbítson és mi kerüljön a
    #: számla tételsorába.
    package_code: Mapped[str | None] = mapped_column(String(50))

    # ── Számlázási adatok ────────────────────────────────────────────────────
    # A vevő a portál fizetési űrlapján adja meg őket, és a sikeres fizetés
    # után EBBŐL állítjuk ki a számlát (lásd services/portal_szamlazz.py). Azért
    # a fizetés sorában ülnek, nem az ügyfélen, mert a számla a vásárlás
    # pillanatának adatait kell hogy őrizze - egy későbbi cégadat-változás nem
    # írhatja át a már kiállított számlát.
    billing_type: Mapped[str | None] = mapped_column(String(20), comment="individual | company")
    billing_name: Mapped[str | None] = mapped_column(String(255))
    billing_zip: Mapped[str | None] = mapped_column(String(20))
    billing_city: Mapped[str | None] = mapped_column(String(120))
    billing_address: Mapped[str | None] = mapped_column(String(255))
    billing_tax_number: Mapped[str | None] = mapped_column(String(50), comment="Csak cégnél")
    billing_email: Mapped[str | None] = mapped_column(String(255))
    #: A Számlázz.hu által adott számla sorszáma - ha ki van töltve, a számla
    #: megvan, és egy ismételt visszahívás nem állít ki másodikat.
    invoice_number: Mapped[str | None] = mapped_column(String(100))

    portal: Mapped["Portal"] = relationship(back_populates="payments")
    revenue: Mapped["Revenue"] = relationship(back_populates="payments")


class PortalFolder(TimestampMixin, Base):
    """Videó/kép-csoportosító mappa egy Portálon belül (pl. "Werkfilm", "Fotók")."""

    __tablename__ = "portal_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    #: SZÜLŐ mappa (a felhasználó kérése: mappán belülre is lehessen mappát
    #: tenni). None = főszintű mappa. A szülő törlésekor a gyerek a főszintre
    #: kerül (SET NULL), nem törlődik vele.
    parent_folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("portal_folders.id", ondelete="SET NULL"), index=True
    )
    #: REJTETT mappa (a felhasználó kérése): az ügyfél a portálon nem látja a
    #: mappát és a tartalmát sem - a belsős (bejelentkezett, portál-jogú)
    #: néző viszont feltűnő jelöléssel igen. A mappa SAJÁT megosztó linkje
    #: szándékosan él (célzottan kiadott link) - ugyanaz az elv, mint a
    #: PortalVideo.rejtett-nél.
    rejtett: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    #: Ha van, a mappa ÖNMAGÁBAN megosztható linkkel (/megosztas/{token}) - a
    #: link birtokosa csak ezt a mappát látja, a portál többi részét nem.
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True)

    portal: Mapped["Portal"] = relationship(back_populates="folders", foreign_keys=[portal_id])
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
    #: Egyetlen videó megosztása linkkel (/megosztas/{token}) - a link
    #: birtokosa csak ezt az egy videót látja.
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True)

    source_key: Mapped[str | None] = mapped_column(String(500), comment="Eredeti mp4 R2 kulcsa")
    mp4_url: Mapped[str | None] = mapped_column(String(500))
    hls_url: Mapped[str | None] = mapped_column(String(500), comment=".m3u8 master playlist URL")
    #: CSAK BELSŐ ELLENŐRZÉSRE (a felhasználó kérése): a rejtett videót az
    #: ügyfél nem látja a portálon (és a mappa-megosztásban sem), pedig a
    #: link már kint van nála - jellemzően a vágó tölti fel így, amíg az
    #: anyag jóváhagyásra vár. A videó SAJÁT megosztó linkje viszont
    #: szándékosan él: azzal küldhető el az ellenőrnek.
    rejtett: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
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
