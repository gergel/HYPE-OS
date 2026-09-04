from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.portal import Brand, PaymentMode, PortalStatus


class PortalBase(BaseModel):
    slug: str
    project_id: int
    share_token: str | None = None
    status: PortalStatus = PortalStatus.DRAFT
    brand: Brand = Brand.HYPE
    expires_at: date | None = None


class PortalCreate(PortalBase):
    password: str | None = None
    title_override: str | None = None
    client_name_override: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    project_date_override: str | None = None
    payment_mode: PaymentMode = PaymentMode.CONTACT


class PortalUpdate(BaseModel):
    status: PortalStatus | None = None
    expires_at: date | None = None
    slug: str | None = None
    password: str | None = None  # "" törli a jelszót
    title_override: str | None = None
    client_name_override: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    project_date_override: str | None = None
    payment_mode: PaymentMode | None = None
    brand: Brand | None = None


class PortalRead(PortalBase):
    id: int

    model_config = {"from_attributes": True}


class PaymentBase(BaseModel):
    payment_request_id: str
    portal_id: int | None = None
    project_id: int | None = None
    revenue_id: int | None = None
    osszeg_huf: float | None = None
    mode: PaymentMode = PaymentMode.CONTACT
    allapot: str | None = None
    barion_payment_id: str | None = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    allapot: str | None = None
    barion_payment_id: str | None = None
    revenue_id: int | None = None


class PaymentRead(PaymentBase):
    id: int

    model_config = {"from_attributes": True}


# ───────── Portal Folder/Video/Image (a Hype-repo-main client-portál 1:1 portolt üzleti logikája) ─────────


class PortalFolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sort_order: int
    #: Rejtett mappa - az ügyfél nem látja (lásd models/portal.PortalFolder.rejtett).
    rejtett: bool = False
    #: Szülő mappa (None = főszint) - lásd models/portal.PortalFolder.parent_folder_id.
    parent_folder_id: int | None = None


class PortalFolderCreate(BaseModel):
    name: str
    #: Melyik mappán BELÜLRE jöjjön létre (None = főszint).
    parent_folder_id: int | None = None


class PortalFolderUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    rejtett: bool | None = None
    parent_folder_id: int | None = None


class PortalVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    folder_id: int | None = None
    mp4_url: str | None = ""
    hls_url: str | None = ""
    thumbnail_url: str | None = ""
    duration_seconds: int = 0
    width: int = 0
    height: int = 0
    resolution_label: str | None = ""
    aspect_ratio_label: str | None = ""
    size_bytes: int = 0
    status: str
    sort_order: int
    #: Csak belső ellenőrzésre - az ügyfél nem látja a portálon (lásd
    #: models/portal.PortalVideo.rejtett).
    rejtett: bool = False


class PortalVideoUpdate(BaseModel):
    title: str | None = None
    sort_order: int | None = None
    folder_id: int | None = None
    rejtett: bool | None = None


class PortalImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str | None = ""
    folder_id: int | None = None
    url: str | None = ""
    thumbnail_url: str | None = ""


class PortalImageUpdate(BaseModel):
    folder_id: int | None = None
    title: str | None = None
    set_folder: bool = False


class ReorderPayload(BaseModel):
    ordered_ids: list[int]


class PortalShareLink(BaseModel):
    url: str
    token: str


class PortalSummary(BaseModel):
    """Az admin projekt-lista (GET /api/v1/portal/admin) egy sora - a Portalhoz
    kötött Project cím/ügyfélnév-mezőire esik vissza, ha nincs override (lásd
    services/portal_storage.py resolve_title/resolve_client_name)."""

    id: int
    slug: str
    project_id: int | None = None
    deliverable_id: int | None = None
    title: str
    client_name: str
    cover_image_url: str
    status: PortalStatus
    brand: Brand
    project_date: str = ""
    expires_at: date | None = None
    payment_mode: PaymentMode
    has_password: bool = False
    # Csak akkor van értéke, ha valaha generáltak megosztó linket ehhez a
    # Portálhoz (lásd portal_admin.py regenerate_share) - a frontend ebből
    # rakja össze a teljes, jelszó nélkül is működő linket (window.location.origin
    # + /p/{slug}?share={token}), pl. a Deliverable "Kész anyag URL" mezőjéhez.
    share_token: str | None = None


class PortalDetail(PortalSummary):
    description: str
    # A nyers felülírás-mezők (nem a resolve_*-tal számolt title/client_name/
    # project_date) - kellenek az admin felületnek, hogy meg tudja mutatni,
    # mi van ténylegesen felülírva, és üresen (None) tudja előtölteni a
    # mezőt, ha nincs override (különben nem lehetne megkülönböztetni "nincs
    # felülírás" és "a felülírás véletlenül ugyanaz, mint a projekt neve" között).
    title_override: str | None = None
    client_name_override: str | None = None
    project_date_override: str | None = None
    videos: list[PortalVideoOut] = []
    folders: list[PortalFolderOut] = []
    images: list[PortalImageOut] = []


class PublicPortal(BaseModel):
    """A nyilvános (bejelentkezés nélküli, /p/{slug}) nézet payloadja."""

    slug: str
    title: str
    client_name: str
    description: str
    cover_image_url: str
    brand: str = "hype"
    project_date: str = ""
    expires_at: date | None = None
    payment_mode: str = "contact"
    videos: list[PortalVideoOut] = []
    folders: list[PortalFolderOut] = []
    images: list[PortalImageOut] = []


class PortalUnlock(BaseModel):
    password: str
