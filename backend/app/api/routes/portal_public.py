"""Média Portál PUBLIKUS végpontok (/api/v1/public/portal/...) - a
Hype-repo-main (különálló client-portál projekt) public.py 1:1 portolt
logikája. FONTOS: ezek a végpontok szándékosan NEM igényelnek HYPE OS
bejelentkezést (a valódi ügyfelek, akiknek a linket küldjük, nem HYPE OS
alkalmazottak) - a jelszavas védelem egy KÜLÖN, portál-hatókörű JWT-vel
történik (lásd _create_unlock_token/_decode_unlock_token), ami nem keverendő
össze az Employee bejelentkezési tokennel (core/security.py)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password
from app.models.portal import Payment, PortalImage, PortalVideo, Portal
from app.schemas.portal import PortalFolderOut, PortalImageOut, PortalVideoOut, PublicPortal
from app.services import portal_barion as barion
from app.services import portal_storage as storage
from app.services import portal_szamlazz as szamlazz
from app.services.portal_resolve import resolve_client_name, resolve_project_date, resolve_title

logger = logging.getLogger("hype_os")

router = APIRouter(prefix="/public/portal", tags=["portal-public"])

# Fizetési csomagok: kód -> (nap, ár HUF, megnevezés)
PACKAGES = {
    "1month": {"days": 30, "amount": 6000, "label": "1 hónap hosszabbítás"},
    "180days": {"days": 180, "amount": 30000, "label": "180 nap hosszabbítás"},
    "1year": {"days": 365, "amount": 50000, "label": "1 év hosszabbítás"},
}

UNLOCK_TOKEN_MINUTES = 60 * 24 * 30  # a böngésző sessionStorage-ban tárolja, de az aláírás is lejár 30 nap után


def _create_unlock_token(portal_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=UNLOCK_TOKEN_MINUTES)
    payload = {"scope": f"portal:{portal_id}", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_unlock_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def _contact_email(portal: Portal) -> str:
    return "hello@contentbee.hu" if portal.brand == "contentbee" else "info@hypestab.hu"


def _is_expired(portal: Portal) -> bool:
    if not portal.expires_at:
        return False
    return datetime.now(timezone.utc).date() > portal.expires_at


def _payment_window_closed(portal: Portal) -> bool:
    """True, ha a lejárat után már több mint 90 nap eltelt - ekkor fizetni sem lehet."""
    if not portal.expires_at:
        return False
    return datetime.now(timezone.utc).date() > (portal.expires_at + timedelta(days=90))


def _serialize(portal: Portal) -> PublicPortal:
    ready = [v for v in portal.videos if v.status == "ready"]
    return PublicPortal(
        slug=portal.slug,
        title=resolve_title(portal),
        client_name=resolve_client_name(portal),
        description=portal.description or "",
        cover_image_url=portal.cover_image_url or "",
        brand=portal.brand,
        project_date=resolve_project_date(portal),
        expires_at=portal.expires_at,
        payment_mode=portal.payment_mode,
        videos=[PortalVideoOut.model_validate(v) for v in ready],
        folders=[PortalFolderOut.model_validate(f) for f in portal.folders],
        images=[PortalImageOut.model_validate(i) for i in portal.images],
    )


@router.get("/{slug}")
def get_public_portal(slug: str, db: Session = Depends(get_db), authorization: str | None = None):
    portal = db.scalar(select(Portal).where(Portal.slug == slug, Portal.status == "live"))
    if not portal:
        raise HTTPException(status_code=404, detail="A portál nem található")

    if _is_expired(portal):
        closed = _payment_window_closed(portal)
        return {
            "expired": True,
            "title": resolve_title(portal),
            "brand": portal.brand,
            "contact_email": _contact_email(portal),
            "payment_mode": "contact" if closed else portal.payment_mode,
            "payment_closed": closed,
            "slug": portal.slug,
        }

    if portal.password_hash:
        if not authorization:
            return {"locked": True, "title": resolve_title(portal), "cover_image_url": portal.cover_image_url or ""}
        try:
            data = _decode_unlock_token(authorization)
            if data.get("scope") != f"portal:{portal.id}":
                raise ValueError
        except (JWTError, ValueError):
            return {"locked": True, "title": resolve_title(portal), "cover_image_url": portal.cover_image_url or ""}

    return {"locked": False, "project": _serialize(portal).model_dump()}


class PortalUnlockPayload(BaseModel):
    password: str


@router.post("/{slug}/unlock")
def unlock(slug: str, payload: PortalUnlockPayload, db: Session = Depends(get_db)):
    portal = db.scalar(select(Portal).where(Portal.slug == slug))
    if not portal or not portal.password_hash:
        raise HTTPException(status_code=404, detail="Nem található")
    if _is_expired(portal):
        raise HTTPException(status_code=410, detail="Lejárt")
    if not verify_password(payload.password, portal.password_hash):
        raise HTTPException(status_code=401, detail="Hibás jelszó")
    return {"token": _create_unlock_token(portal.id)}


@router.get("/share/{token}")
def get_by_share(token: str, db: Session = Depends(get_db)):
    portal = db.scalar(select(Portal).where(Portal.share_token == token))
    if not portal:
        raise HTTPException(status_code=404, detail="Nem található")
    if _is_expired(portal):
        return {
            "expired": True,
            "title": resolve_title(portal),
            "brand": portal.brand,
            "contact_email": _contact_email(portal),
            "payment_mode": portal.payment_mode,
            "slug": portal.slug,
        }
    return {"locked": False, "project": _serialize(portal).model_dump()}


class BillingPayload(BaseModel):
    """A vevő számlázási adatai a portál fizetési űrlapjáról.

    A számlához mindig kell név és cím; cégnél az adószám is - enélkül a
    Számlázz.hu sem tudna érvényes számlát kiállítani, ezért itt kérjük be, a
    fizetés INDÍTÁSA előtt, nem utólag."""

    type: str = "individual"
    name: str = ""
    zip: str = ""
    city: str = ""
    address: str = ""
    tax_number: str = ""
    email: str = ""


class PayPayload(BaseModel):
    package: str
    billing: BillingPayload | None = None


@router.post("/{slug}/pay")
def start_payment(slug: str, payload: PayPayload, db: Session = Depends(get_db)):
    portal = db.scalar(select(Portal).where(Portal.slug == slug))
    if not portal:
        raise HTTPException(status_code=404, detail="Nem található")
    if portal.payment_mode != "paid":
        raise HTTPException(status_code=400, detail="Ehhez a portálhoz nincs bekapcsolva a fizetés")

    pkg = PACKAGES.get(payload.package)
    if not pkg:
        raise HTTPException(status_code=400, detail="Érvénytelen csomag")

    # A számlázási adatokat a fizetés INDÍTÁSAKOR kérjük be és mentjük el: a
    # Barion visszahívásában már csak egy azonosító jön, akkor nincs kitől
    # megkérdezni, kinek szóljon a számla.
    billing = payload.billing or BillingPayload()
    hianyzik = [
        cimke
        for cimke, ertek in (
            ("név", billing.name),
            ("irányítószám", billing.zip),
            ("település", billing.city),
            ("cím", billing.address),
        )
        if not (ertek or "").strip()
    ]
    if hianyzik:
        raise HTTPException(status_code=400, detail=f"Hiányzó számlázási adat: {', '.join(hianyzik)}.")
    if billing.type == "company" and not billing.tax_number.strip():
        raise HTTPException(status_code=400, detail="Cégnél az adószám is kötelező.")

    ts = int(datetime.now(timezone.utc).timestamp())
    payment_request_id = f"{portal.id}_{payload.package}_{ts}"

    front = settings.frontend_base_url.rstrip("/")
    api = settings.api_base_url.rstrip("/")
    # A visszairányítás vissza is hozza, MI sikerült: ebből tudja a portál
    # megköszönni a vásárlást és elküldeni a Barion Pixel purchase eseményét
    # (a fizetés tényét a szerver a visszahívásból tudja, ez csak a nézőnek szól).
    redirect_url = (
        f"{front}/p/{portal.slug}?paid=1&pkg={payload.package}"
        f"&amt={pkg['amount']}&pid={payment_request_id}"
    )
    callback_url = f"{api}/api/v1/public/portal/barion/callback"

    data = barion.start_payment(
        payment_request_id=payment_request_id,
        amount=pkg["amount"],
        title=pkg["label"],
        redirect_url=redirect_url,
        callback_url=callback_url,
    )
    if data.get("Errors"):
        raise HTTPException(status_code=502, detail="Fizetési szolgáltató hiba")
    gateway_url = data.get("GatewayUrl")
    if not gateway_url:
        raise HTTPException(status_code=502, detail="Nincs GatewayUrl a válaszban")

    db.add(
        Payment(
            payment_request_id=payment_request_id,
            portal_id=portal.id,
            project_id=portal.project_id,
            osszeg_huf=pkg["amount"],
            mode=portal.payment_mode,
            allapot="started",
            barion_payment_id=data.get("PaymentId", ""),
            package_code=payload.package,
            billing_type=billing.type,
            billing_name=billing.name.strip(),
            billing_zip=billing.zip.strip(),
            billing_city=billing.city.strip(),
            billing_address=billing.address.strip(),
            billing_tax_number=billing.tax_number.strip() if billing.type == "company" else "",
            billing_email=billing.email.strip(),
        )
    )
    db.commit()
    return {"gateway_url": gateway_url}


@router.post("/barion/callback")
async def barion_callback(request: Request, db: Session = Depends(get_db)):
    qp = request.query_params
    payment_id = qp.get("paymentId") or qp.get("PaymentId") or qp.get("paymentid")
    if not payment_id:
        try:
            body = await request.json()
            payment_id = body.get("PaymentId") or body.get("paymentId")
        except Exception:
            try:
                form = await request.form()
                payment_id = form.get("PaymentId") or form.get("paymentId")
            except Exception:
                payment_id = None
    if not payment_id:
        return {"ok": True}

    state = barion.get_payment_state(payment_id)
    status = state.get("Status")
    request_id = state.get("PaymentRequestId") or ""

    if status == "Succeeded":
        parts = request_id.split("_")
        if len(parts) >= 2:
            try:
                portal_id = int(parts[0])
            except ValueError:
                portal_id = None
            pkg = PACKAGES.get(parts[1])
            portal = db.get(Portal, portal_id) if portal_id is not None else None
            if portal and pkg:
                today = datetime.now(timezone.utc).date()
                base_date = portal.expires_at if (portal.expires_at and portal.expires_at > today) else today
                portal.expires_at = base_date + timedelta(days=pkg["days"])
                db.commit()

            _fizetes_lezarasa(db, request_id, pkg)

    return {"ok": True}


def _fizetes_lezarasa(db: Session, request_id: str, pkg: dict | None) -> None:
    """A sikeres fizetés rögzítése és a számla kiállítása.

    A Barion többször is meghívhat ugyanarra a fizetésre, ezért mindkét lépés
    egyszeri: a már kifizetettként jelölt sort nem írjuk át, és ha a számlaszám
    megvan, nem állítunk ki másodikat.

    A számlázás hibája NEM buktatja meg a visszahívást: a pénz megérkezett, a
    hosszabbítás jár - a számlát legfeljebb kézzel kell pótolni. Ezért csak
    naplózunk."""
    payment = db.scalar(select(Payment).where(Payment.payment_request_id == request_id))
    if payment is None or payment.allapot == "succeeded":
        return
    payment.allapot = "succeeded"
    db.commit()

    if payment.invoice_number:
        return
    eredmeny = szamlazz.create_invoice(
        buyer_name=payment.billing_name or "",
        buyer_zip=payment.billing_zip or "",
        buyer_city=payment.billing_city or "",
        buyer_address=payment.billing_address or "",
        buyer_tax_number=payment.billing_tax_number or "",
        buyer_email=payment.billing_email or "",
        item_name=(pkg or {}).get("label") or "Tárhely-hosszabbítás",
        gross_amount=int(payment.osszeg_huf or 0),
    )
    if eredmeny.get("ok"):
        payment.invoice_number = eredmeny.get("invoice_number", "")
        db.commit()
    else:
        logger.warning("A számla nem készült el (%s): %s", request_id, eredmeny.get("error"))


downloads_router = APIRouter(prefix="/public", tags=["portal-public"])


@downloads_router.get("/portal-videos/{video_id}/download")
def public_video_download(video_id: int, db: Session = Depends(get_db)):
    video = db.get(PortalVideo, video_id)
    if not video or not video.source_key:
        raise HTTPException(status_code=404, detail="Nem található")
    safe = (video.title or "video").replace('"', "").replace("\n", " ")
    return {"url": storage.presigned_download(video.source_key, f"{safe}.mp4")}


@downloads_router.get("/portal-images/{image_id}/download")
def public_image_download(image_id: int, db: Session = Depends(get_db)):
    image = db.get(PortalImage, image_id)
    if not image or not image.key:
        raise HTTPException(status_code=404, detail="Nem található")
    ext = image.key.split(".")[-1] if "." in image.key else "jpg"
    filename = f"{image.title or 'image'}.{ext}"
    return {"url": storage.presigned_download(image.key, filename)}
