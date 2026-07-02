from datetime import date

from pydantic import BaseModel

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


class PortalUpdate(BaseModel):
    status: PortalStatus | None = None
    expires_at: date | None = None


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
