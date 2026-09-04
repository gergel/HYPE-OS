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

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
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


def _belsos_nezo(db: Session, hype_token: str | None) -> bool:
    """BELSŐS NÉZŐ-e a portál látogatója: bejelentkezett HYPE OS felhasználó,
    akinek van hozzáférése a Média Portál oldalhoz. Neki a rejtett videók/
    mappák is látszanak a portálon, feltűnő jelöléssel (a felhasználó
    kérése) - az ügyfélnek nem. A token hibája nem hiba: olyankor egyszerűen
    ügyfél-nézetet adunk."""
    if not hype_token:
        return False
    try:
        from app.core.security import _oldal_muveletei
        from app.models.employee import Employee
        from app.models.user_access import PageAccessConfig

        payload = jwt.decode(hype_token, settings.secret_key, algorithms=[settings.algorithm])
        employee = db.get(Employee, int(payload.get("sub") or 0))
        if employee is None or not employee.is_active:
            return False
        config = db.scalar(select(PageAccessConfig).where(PageAccessConfig.employee_id == employee.id))
        if config is None or config.page_permissions is None:
            return True
        return _oldal_muveletei(config.page_permissions, "/media-portal") is not None
    except Exception:  # noqa: BLE001 - rossz/lejárt token = sima ügyfél-nézet
        return False


def _rejtett_mappak_rekurzivan(portal: Portal) -> set[int]:
    """A rejtett mappák ÉS az összes almappájuk id-i - egy rejtett mappa a
    teljes tartalmával (az almappáival együtt) tűnik el az ügyfél elől."""
    gyerekek: dict[int | None, list[int]] = {}
    for f in portal.folders:
        gyerekek.setdefault(f.parent_folder_id, []).append(f.id)
    rejtett = {f.id for f in portal.folders if f.rejtett}
    sor = list(rejtett)
    while sor:
        szulo = sor.pop()
        for gyerek in gyerekek.get(szulo, []):
            if gyerek not in rejtett:
                rejtett.add(gyerek)
                sor.append(gyerek)
    return rejtett


def _serialize(portal: Portal, belsos: bool = False) -> PublicPortal:
    # A REJTETT (csak belső ellenőrzésre feltöltött) videó és a REJTETT mappa
    # (a tartalmával és az almappáival együtt) nem megy ki az ügyfélnek (a
    # felhasználó kérése) - hiába él nála a portál linkje. A BELSŐS néző
    # viszont mindent lát, a rejtett elemeket a felület feltűnően jelöli.
    rejtett_mappak = _rejtett_mappak_rekurzivan(portal)
    if belsos:
        ready = [v for v in portal.videos if v.status == "ready"]
        folders = list(portal.folders)
        images = list(portal.images)
    else:
        ready = [
            v
            for v in portal.videos
            if v.status == "ready" and not v.rejtett and v.folder_id not in rejtett_mappak
        ]
        folders = [f for f in portal.folders if f.id not in rejtett_mappak]
        images = [i for i in portal.images if i.folder_id not in rejtett_mappak]
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
        folders=[PortalFolderOut.model_validate(f) for f in folders],
        images=[PortalImageOut.model_validate(i) for i in images],
    )


@router.get("/{slug}")
def get_public_portal(
    slug: str,
    db: Session = Depends(get_db),
    authorization: str | None = None,
    # A BELSŐS néző HYPE OS tokenje (a felhasználó kérése): vele a rejtett
    # videók/mappák is jönnek, rejtett-jelöléssel - lásd _belsos_nezo.
    belsos_token: str | None = None,
):
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

    return {"locked": False, "project": _serialize(portal, belsos=_belsos_nezo(db, belsos_token)).model_dump()}


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

    # A fizetés az ügyfél-oldali portál-domainen zajlik, oda is kell
    # visszatérnie - a Barionnál regisztrált domainnek ezzel kell egyeznie.
    front = settings.portal_front_base
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


def _stream_fajl(key: str, filename: str, fallback_tipus: str) -> StreamingResponse:
    """A fájl átfolyatása a backenden (lásd portal_storage.stream_object) - a
    tömeges ZIP letöltés TARTALÉK útvonala: a böngésző a presigned R2 URL-eket
    csak akkor tudja fetch()-elni, ha a bucketen van CORS-szabály a portál
    originjére; ha nincs, a frontend erre a végpontra esik vissza (lásd
    lib/portalUtils.ts fetchFileWithFallback), ami a backend saját
    CORSMiddleware-én át mindig működik."""
    try:
        chunkok, meret, tipus = storage.stream_object(key)
    except storage.R2NotConfiguredError:
        raise
    except ClientError as exc:
        if (exc.response.get("Error") or {}).get("Code") in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="A fájl nem található a tárhelyen") from exc
        raise
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if meret:
        headers["Content-Length"] = str(meret)
    return StreamingResponse(chunkok, media_type=tipus or fallback_tipus, headers=headers)


@downloads_router.get("/portal-videos/{video_id}/file")
def public_video_file(video_id: int, db: Session = Depends(get_db)):
    video = db.get(PortalVideo, video_id)
    if not video or not video.source_key:
        raise HTTPException(status_code=404, detail="Nem található")
    safe = (video.title or "video").replace('"', "").replace("\n", " ")
    return _stream_fajl(video.source_key, f"{safe}.mp4", "video/mp4")


@downloads_router.get("/portal-images/{image_id}/file")
def public_image_file(image_id: int, db: Session = Depends(get_db)):
    image = db.get(PortalImage, image_id)
    if not image or not image.key:
        raise HTTPException(status_code=404, detail="Nem található")
    ext = image.key.split(".")[-1] if "." in image.key else "jpg"
    safe = (image.title or "image").replace('"', "").replace("\n", " ")
    return _stream_fajl(image.key, f"{safe}.{ext}", "image/jpeg")


# ─────────────────────────────────────────────────────────────────────────────
# FELTÖLTŐ LINK (a felhasználó kérése): aki a linket kapja, mappát hozhat
# létre és feltölthet a portálra (vagy csak a kijelölt mappájába) - törölni
# viszont SEMMIT nem tud (ilyen végpont ezen a tokenen nincs is).
# ─────────────────────────────────────────────────────────────────────────────


def _feltolto_portal(db: Session, token: str) -> Portal:
    portal = db.scalar(select(Portal).where(Portal.feltolto_token == token))
    if portal is None:
        raise HTTPException(status_code=404, detail="Ez a feltöltő link nem él (visszavonták vagy hibás).")
    return portal


@router.get("/feltoltes/{token}")
def feltoltes_adatok(token: str, db: Session = Depends(get_db)):
    """Mit lát a feltöltő link birtokosa: a portál címe és a mappák (a
    kijelölt mappára szűkítve, ha a link csak oda szól)."""
    portal = _feltolto_portal(db, token)
    mappak = [f for f in portal.folders if portal.feltolto_folder_id in (None, f.id)]

    # Beágyazott mappánál a TELJES útvonal a név ("Szülő / Gyerek") - a lapos
    # listában enélkül nem derülne ki, melyik mappán belül van.
    nev_szerint = {f.id: f for f in portal.folders}

    def utvonal(f) -> str:
        reszek = [f.name or "Névtelen mappa"]
        szulo_id = f.parent_folder_id
        while szulo_id is not None and szulo_id in nev_szerint:
            szulo = nev_szerint[szulo_id]
            reszek.append(szulo.name or "Névtelen mappa")
            szulo_id = szulo.parent_folder_id
        return " / ".join(reversed(reszek))

    return {
        "title": resolve_title(portal),
        "brand": portal.brand,
        "csak_mappa": portal.feltolto_folder_id is not None,
        "folders": [
            {"id": f.id, "name": utvonal(f), "video_db": len(f.videos), "kep_db": len(f.images)} for f in mappak
        ],
    }


class FeltoltesMappaIn(BaseModel):
    name: str


@router.post("/feltoltes/{token}/mappa")
def feltoltes_mappa(token: str, payload: FeltoltesMappaIn, db: Session = Depends(get_db)):
    from app.models.portal import PortalFolder

    portal = _feltolto_portal(db, token)
    if portal.feltolto_folder_id is not None:
        raise HTTPException(status_code=403, detail="Ez a link csak egy megadott mappába enged feltölteni.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Adj nevet a mappának.")
    max_order = max([f.sort_order for f in portal.folders], default=-1)
    folder = PortalFolder(portal_id=portal.id, name=payload.name.strip(), sort_order=max_order + 1)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"id": folder.id, "name": folder.name}


def _feltoltes_cel_mappa(db: Session, portal: Portal, folder_id: int | None):
    """A feltöltés cél-mappája - a link hatókörén belül."""
    from app.models.portal import PortalFolder

    if portal.feltolto_folder_id is not None:
        # Mappára szűkített link: mindegy, mit kért, oda megy.
        return portal.feltolto_folder_id
    if folder_id is None:
        return None
    folder = db.get(PortalFolder, folder_id)
    if folder is None or folder.portal_id != portal.id:
        raise HTTPException(status_code=404, detail="Ez a mappa nem ehhez a portálhoz tartozik.")
    return folder.id


@router.post("/feltoltes/{token}/video")
async def feltoltes_video(
    token: str,
    file: UploadFile = File(...),
    folder_id: int | None = Form(None),
    title: str | None = Form(None),
    # CSAK BELSŐ ELLENŐRZÉSRE (a felhasználó kérése): a vágó a feltöltő
    # oldalon bejelölheti, hogy az ügyfél még ne lássa - lásd
    # models/portal.PortalVideo.rejtett.
    rejtett: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Videó feltöltése a feltöltő linkkel - ugyanaz a tároló + feldolgozó
    csővezeték, mint az admin feltöltésnél (lásd portal_admin.upload_video)."""
    import os as _os
    import tempfile as _tempfile

    from app.api.routes.portal_admin import _enqueue_processing

    portal = _feltolto_portal(db, token)
    cel_mappa = _feltoltes_cel_mappa(db, portal, folder_id)
    max_order = max([v.sort_order for v in portal.videos], default=-1)
    video = PortalVideo(
        portal_id=portal.id,
        folder_id=cel_mappa,
        title=(title or "").strip() or _os.path.splitext(file.filename or "Untitled")[0],
        status="processing",
        sort_order=max_order + 1,
        rejtett=rejtett,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    source_key = f"videos/{video.id}/upload.mp4"
    with _tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    storage.upload_file(tmp_path, source_key, "video/mp4")
    _os.unlink(tmp_path)
    video.source_key = source_key
    db.commit()
    _enqueue_processing(video.id, source_key)
    return {"id": video.id, "title": video.title, "status": video.status}


@router.post("/feltoltes/{token}/kep")
async def feltoltes_kep(
    token: str,
    file: UploadFile = File(...),
    folder_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Kép feltöltése a feltöltő linkkel - a bélyegkép-készítés ugyanaz, mint
    az admin oldalon (lásd portal_admin.upload_image)."""
    import io as _io

    from PIL import Image as PILImage

    portal = _feltolto_portal(db, token)
    cel_mappa = _feltoltes_cel_mappa(db, portal, folder_id)
    image = PortalImage(portal_id=portal.id, folder_id=cel_mappa)
    db.add(image)
    db.flush()

    data = await file.read()
    ext = (file.filename or "image.jpg").split(".")[-1].lower()
    key = f"images/{image.id}/original.{ext}"
    storage.upload_bytes(data, key, file.content_type or "image/jpeg")
    thumb_url = ""
    try:
        img = PILImage.open(_io.BytesIO(data))
        img = img.convert("RGB")
        img.thumbnail((1200, 1200))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=True)
        thumb_key = f"images/{image.id}/thumb.jpg"
        storage.upload_bytes(buf.getvalue(), thumb_key, "image/jpeg")
        thumb_url = storage.public_url(thumb_key)
    except Exception:  # noqa: BLE001 - bélyegkép nélkül is él a kép
        thumb_url = ""
    max_order = max([i.sort_order for i in portal.images], default=-1)
    image.title = (file.filename or "").rsplit(".", 1)[0]
    image.url = storage.public_url(key)
    image.thumbnail_url = thumb_url
    image.key = key
    image.size_bytes = len(data)
    image.sort_order = max_order + 1
    db.commit()
    return {"id": image.id, "title": image.title}


# ─────────────────────────────────────────────────────────────────────────────
# RÉSZ-MEGOSZTÁS: egy mappa vagy egy videó a saját linkjén - a link birtokosa
# csak azt látja, a portál többi részét nem.
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/megosztas/{token}")
def megosztas(token: str, db: Session = Depends(get_db)):
    from app.models.portal import PortalFolder

    folder = db.scalar(select(PortalFolder).where(PortalFolder.share_token == token))
    if folder is not None:
        portal = folder.portal
        # A rejtett videó a mappa-megosztásból is kimarad (lásd _serialize).
        ready = [v for v in folder.videos if v.status == "ready" and not v.rejtett]
        project = PublicPortal(
            slug=portal.slug,
            title=f"{resolve_title(portal)} – {folder.name}" if folder.name else resolve_title(portal),
            client_name=resolve_client_name(portal),
            description="",
            cover_image_url=portal.cover_image_url or "",
            brand=portal.brand,
            project_date=resolve_project_date(portal),
            expires_at=portal.expires_at,
            payment_mode="contact",
            videos=[PortalVideoOut.model_validate(v) for v in ready],
            folders=[PortalFolderOut.model_validate(folder)],
            images=[PortalImageOut.model_validate(i) for i in folder.images],
        )
        return {"tipus": "mappa", "project": project.model_dump()}

    # A videó SAJÁT megosztó linkje a rejtett videónál is él (szándékosan):
    # ezt a linket kézzel adja ki valaki (pl. az ellenőrnek) - a rejtés a
    # PORTÁL nézete elől takar, nem a célzottan megosztott link elől.
    video = db.scalar(select(PortalVideo).where(PortalVideo.share_token == token))
    if video is not None and video.status == "ready":
        portal = video.portal
        project = PublicPortal(
            slug=portal.slug,
            title=video.title or resolve_title(portal),
            client_name=resolve_client_name(portal),
            description="",
            cover_image_url=portal.cover_image_url or "",
            brand=portal.brand,
            project_date=resolve_project_date(portal),
            expires_at=portal.expires_at,
            payment_mode="contact",
            videos=[PortalVideoOut.model_validate(video)],
            folders=[],
            images=[],
        )
        return {"tipus": "video", "project": project.model_dump()}

    raise HTTPException(status_code=404, detail="Ez a megosztó link nem él (visszavonták vagy hibás).")


class ReszletLinkIn(BaseModel):
    """Mappa VAGY videó linkjének kérése a portál-nézetből (a felhasználó
    kérése: ne csak adminból lehessen link-et másolni). Jelszavas portálnál a
    feloldó tokent is kérjük - a link-készítés ne kerülje meg a jelszót."""

    folder_id: int | None = None
    video_id: int | None = None
    authorization: str | None = None


@router.post("/{slug}/reszlet-link")
def reszlet_link(slug: str, payload: ReszletLinkIn, db: Session = Depends(get_db)):
    import uuid

    from app.models.portal import PortalFolder

    portal = db.scalar(select(Portal).where(Portal.slug == slug, Portal.status == "live"))
    if not portal:
        raise HTTPException(status_code=404, detail="A portál nem található")
    if portal.password_hash:
        try:
            data = _decode_unlock_token(payload.authorization or "")
            if data.get("scope") != f"portal:{portal.id}":
                raise ValueError
        except (JWTError, ValueError):
            raise HTTPException(status_code=401, detail="A link-készítéshez előbb old fel a portált a jelszóval.")

    front = settings.portal_front_base
    if payload.folder_id is not None:
        folder = db.get(PortalFolder, payload.folder_id)
        if folder is None or folder.portal_id != portal.id:
            raise HTTPException(status_code=404, detail="Ez a mappa nem ehhez a portálhoz tartozik.")
        if not folder.share_token:
            folder.share_token = uuid.uuid4().hex
            db.commit()
        return {"url": f"{front}/megosztas/{folder.share_token}"}
    if payload.video_id is not None:
        video = db.get(PortalVideo, payload.video_id)
        if video is None or video.portal_id != portal.id:
            raise HTTPException(status_code=404, detail="Ez a videó nem ehhez a portálhoz tartozik.")
        if not video.share_token:
            video.share_token = uuid.uuid4().hex
            db.commit()
        return {"url": f"{front}/megosztas/{video.share_token}"}
    raise HTTPException(status_code=400, detail="Adj meg mappát vagy videót.")
