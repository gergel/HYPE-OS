"""Média Portál admin végpontok - a Hype-repo-main (különálló client-portál
projekt) admin.py 1:1 portolt üzleti logikája, két lényegi különbséggel:

1. Nincs külön Admin-tábla/JWT-bejelentkezés - a meglévő HYPE OS
   Employee-auth-ot használja (get_current_user + require_page_action
   "/media-portal" oldalra), ugyanúgy, mint minden más modul.
2. Egy Portal mindig egy MEGLÉVŐ HYPE OS Project-hez van kötve (1:1) - nincs
   szabadon kitöltött cím/ügyfélnév, azok a Project mezőire esnek vissza,
   hacsak az admin felül nem írja (lásd services/portal_resolve.py)."""

from __future__ import annotations

import io
import os
import tempfile
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image as PILImage
from pydantic import BaseModel
from slugify import slugify
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, get_current_user, hash_password, require_page_action
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.portal import Portal, PortalFolder, PortalImage, PortalVideo
from app.models.project import Project
from app.schemas.portal import (
    PortalDetail,
    PortalFolderCreate,
    PortalFolderOut,
    PortalFolderUpdate,
    PortalImageOut,
    PortalImageUpdate,
    PortalShareLink,
    PortalSummary,
    PortalVideoOut,
    PortalVideoUpdate,
    ReorderPayload,
)
from app.services import portal_notion, portal_storage as storage
from app.services.portal_resolve import resolve_client_name, resolve_project_date, resolve_title
from app.workers.portal_tasks import process_video_task

router = APIRouter(prefix="/portal-admin", tags=["portal-admin"])

PAGE = "/media-portal"

#: A durva admin/operator szerepkör-kapu itt nem érvényes: akinek admin a
#: Beállításokban TELJES hozzáférést adott a Portál oldalra, az mindent
#: tud - egyéni portált létrehozni, feltölteni, törölni is. Ugyanaz az
#: elv, mint az Utómunkánál (lásd routes/postproduction.py
#: _MINDEN_SZEREPKOR); a page_permissions-védelem változatlanul él.
_MINDEN_SZEREPKOR = tuple(Role)


def _summary(p: Portal) -> PortalSummary:
    return PortalSummary(
        id=p.id,
        slug=p.slug,
        project_id=p.project_id,
        deliverable_id=p.deliverable_id,
        title=resolve_title(p),
        client_name=resolve_client_name(p),
        cover_image_url=p.cover_image_url or "",
        status=p.status,
        brand=p.brand,
        project_date=resolve_project_date(p),
        expires_at=p.expires_at,
        payment_mode=p.payment_mode,
        has_password=bool(p.password_hash),
        share_token=p.share_token,
    )


def _detail(p: Portal) -> PortalDetail:
    return PortalDetail(
        **_summary(p).model_dump(),
        description=p.description or "",
        title_override=p.title_override,
        client_name_override=p.client_name_override,
        project_date_override=p.project_date_override,
        videos=[PortalVideoOut.model_validate(v) for v in p.videos],
        folders=[PortalFolderOut.model_validate(f) for f in p.folders],
        images=[PortalImageOut.model_validate(i) for i in p.images],
    )


def _get_portal_or_404(db: Session, portal_id: int) -> Portal:
    portal = db.get(Portal, portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="Portál nem található")
    return portal


def _enqueue_processing(video_id: int, source_key: str) -> None:
    """A videó feltöltése (R2 + DB sor) ekkorra már sikeresen megtörtént -
    ha a Celery task queue-ba tétele elhasal (pl. mert a REDIS_URL nincs
    beállítva, vagy a worker service nem fut), ne egy nyers, kontextus
    nélküli 500-at kapjon a kliens, hanem egyértelmű, javítható hibaüzenetet."""
    try:
        process_video_task.delay(video_id, source_key)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "A videó feltöltve, de a feldolgozás nem indult el, mert a háttér-feldolgozó "
                "szolgáltatás (Redis/Celery worker) nincs beállítva vagy nem érhető el. "
                "Ellenőrizd a REDIS_URL környezeti változót és hogy a Celery worker service fut-e."
            ),
        ) from exc


# ---------------- Portálok (projektenként) ----------------


@router.get("", response_model=list[PortalSummary])
def list_portals(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    portals = db.query(Portal).order_by(Portal.created_at.desc()).all()
    return [_summary(p) for p in portals]


class PortalAdminCreate(BaseModel):
    project_id: int | None = None
    slug: str | None = None
    password: str | None = None
    # Csak akkor kötelező (és csak akkor van jelentése), ha nincs project_id -
    # egy Projekthez kötött Portálnál ezek a Project saját mezőire esnek
    # vissza (lásd services/portal_resolve.py), egy "kézzel" létrehozott,
    # Projekt nélküli Portálnál viszont ezek adják az egyetlen adatforrást.
    title: str | None = None
    client_name: str | None = None
    project_date: str | None = None


@router.post("", response_model=PortalSummary, status_code=201)
def create_portal(
    payload: PortalAdminCreate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    if payload.project_id is not None:
        project = db.get(Project, payload.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projekt nem található")
        if project.portal is not None:
            raise HTTPException(status_code=400, detail="Ennek a projektnek már van Portálja")
        slug_base = payload.slug or slugify(project.nev)
        project_id = project.id
        title_override = client_name_override = project_date_override = None
    else:
        if not (payload.title or "").strip():
            raise HTTPException(status_code=400, detail="A Portál címe kötelező, ha nincs projekt kiválasztva")
        slug_base = payload.slug or slugify(payload.title or "")
        project_id = None
        title_override = payload.title
        client_name_override = payload.client_name
        project_date_override = payload.project_date

    slug = slug_base
    if db.query(Portal).filter(Portal.slug == slug).first():
        slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"

    portal = Portal(
        project_id=project_id,
        slug=slug,
        status="live",  # az eredeti Hype-repo-main is közvetlenül "live"-ként hozza létre, nincs külön "vázlat" lépés
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=date.today() + timedelta(days=30),
        title_override=title_override,
        client_name_override=client_name_override,
        project_date_override=project_date_override,
    )
    db.add(portal)
    db.commit()
    db.refresh(portal)
    return _summary(portal)


class PortalFromDeliverableCreate(BaseModel):
    password: str | None = None
    #: A forgatás dátuma "ÉÉÉÉ.HH.NN." formában - CSAK akkor kell megadni, ha
    #: az utómunkához nincs forgatás (Project) kötve, ahonnan a dátum magától
    #: kiolvasható (a frontend ilyenkor felugró ablakban kéri be).
    forgatas_datum: str | None = None


@router.post("/from-deliverable/{deliverable_id}", response_model=PortalSummary, status_code=201)
def create_portal_from_deliverable(
    deliverable_id: int,
    payload: PortalFromDeliverableCreate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """Az Utómunka oldalon lévő "Portál létrehozása" gomb - egy Portált hoz
    létre KÖZVETLENÜL egy Deliverable-hez kötve (nem a mögöttes Projekthez,
    lásd Portal.deliverable_id kommentje), és a Portál publikus linkjét
    automatikusan beírja a Deliverable "Kész anyag URL" mezőjébe, hogy a
    vágónak ne kelljen külön másolnia/beillesztenie."""
    deliverable = db.get(Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="Utómunka nem található")
    if deliverable.portal is not None:
        raise HTTPException(status_code=400, detail="Ehhez az utómunkához már tartozik Portál")

    title = deliverable.projekt_neve or f"Utómunka #{deliverable.id}"
    # Az ügyfél mező SZÁNDÉKOSAN ÜRESEN indul (a felhasználó kérése): a
    # projektkód ügyfele sokszor csak import-gyűjtő ("Ismeretlen ügyfél"),
    # és az ügyfélnek kimenő oldalon rosszabb egy téves név, mint az üres -
    # ha kell, az admin utólag kitölti a Portál adatainál.
    #
    # A Portálon megjelenő dátum a FORGATÁS dátuma (a felhasználó kérése), nem
    # az utómunka határideje: ha az utómunkához forgatás (Project) van kötve,
    # onnan olvassuk ki magától; ha nincs, a frontend felugró ablakban kéri be
    # KÖTELEZŐEN (payload.forgatas_datum) - dátum nélkül nem jön létre Portál.
    projekt_forgatas = deliverable.project.forgatas_datuma if deliverable.project else None
    if projekt_forgatas is not None:
        project_date = projekt_forgatas.strftime("%Y.%m.%d")
    elif (payload.forgatas_datum or "").strip():
        project_date = (payload.forgatas_datum or "").strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Add meg a forgatás dátumát - az utómunkához nincs forgatás kötve, ahonnan ki tudnánk olvasni",
        )

    slug_base = slugify(title)
    slug = slug_base
    if db.query(Portal).filter(Portal.slug == slug).first():
        slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"

    portal = Portal(
        deliverable_id=deliverable.id,
        slug=slug,
        share_token=uuid.uuid4().hex,
        status="live",
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=date.today() + timedelta(days=30),
        title_override=title,
        client_name_override=None,
        project_date_override=project_date,
    )
    db.add(portal)
    db.commit()
    db.refresh(portal)

    # A "Kész anyag URL" mező kitöltését a FRONTEND végzi (lásd
    # CreatePortalButton.tsx), a böngésző window.location.origin-jéből
    # összerakva a teljes, abszolút linket - itt a backend nem tudja
    # megbízhatóan összerakni (a settings.frontend_base_url gyakran nincs
    # beállítva minden környezetben, és akkor csak a relatív "/p/{slug}..."
    # útvonal kerülne a mezőbe, ami önmagában nem küldhető ki a megrendelőnek).
    return _summary(portal)


@router.get("/{portal_id}", response_model=PortalDetail)
def get_portal(
    portal_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    return _detail(_get_portal_or_404(db, portal_id))


class PortalAdminUpdate(BaseModel):
    status: str | None = None
    brand: str | None = None
    slug: str | None = None
    password: str | None = None
    title_override: str | None = None
    client_name_override: str | None = None
    description: str | None = None
    project_date_override: str | None = None
    payment_mode: str | None = None
    expires_at: date | None = None


@router.patch("/{portal_id}", response_model=PortalSummary)
def update_portal(
    portal_id: int,
    payload: PortalAdminUpdate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    portal = _get_portal_or_404(db, portal_id)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        pw = data.pop("password")
        portal.password_hash = hash_password(pw) if pw else None
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    for k, v in data.items():
        setattr(portal, k, v)
    db.commit()
    db.refresh(portal)
    return _summary(portal)


@router.delete("/{portal_id}", status_code=204)
def delete_portal(
    portal_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR))
):
    portal = _get_portal_or_404(db, portal_id)
    for v in portal.videos:
        storage.delete_prefix(f"videos/{v.id}")
    for img in portal.images:
        storage.delete_prefix(f"images/{img.id}")
    db.delete(portal)
    db.commit()


@router.post("/{portal_id}/cover")
async def upload_cover(
    portal_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    portal = _get_portal_or_404(db, portal_id)
    ext = os.path.splitext(file.filename or "cover.jpg")[1] or ".jpg"
    key = f"covers/{portal_id}/cover{ext}"
    content_type = file.content_type or "image/jpeg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    url = storage.upload_file(tmp_path, key, content_type)
    os.unlink(tmp_path)
    portal.cover_image_url = url
    db.commit()
    return {"cover_image_url": url}


@router.delete("/{portal_id}/cover")
def delete_cover(
    portal_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR))
):
    portal = _get_portal_or_404(db, portal_id)
    storage.delete_prefix(f"covers/{portal_id}")
    portal.cover_image_url = ""
    db.commit()
    return {"cover_image_url": ""}


@router.post("/{portal_id}/share", response_model=PortalShareLink)
def regenerate_share(
    portal_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR))
):
    portal = _get_portal_or_404(db, portal_id)
    portal.share_token = uuid.uuid4().hex
    db.commit()
    from app.core.config import settings

    # A megosztó link az ÜGYFÉLNEK megy, tehát a portál saját domainjére mutat
    # (settings.portal_base_url), nem az admin felületére.
    front = settings.portal_front_base
    return PortalShareLink(token=portal.share_token, url=f"{front}/p/{portal.slug}?share={portal.share_token}")


# ---------------- Feltöltő link és rész-megosztás (a felhasználó kérése) ----


def _portal_front() -> str:
    from app.core.config import settings

    return settings.portal_front_base


class FeltoltoLinkIn(BaseModel):
    #: Ha meg van adva, a link CSAK ebbe a mappába enged feltölteni (és új
    #: mappát sem hozhat létre); üresen az egész portálra érvényes.
    folder_id: int | None = None


@router.post("/{portal_id}/feltolto-link", response_model=PortalShareLink)
def feltolto_link(
    portal_id: int,
    payload: FeltoltoLinkIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """FELTÖLTŐ link: aki megkapja, mappákat hozhat létre és feltölthet a
    portálra (vagy csak a megadott mappába), de semmit nem törölhet - lásd
    routes/portal_public.py "feltoltes" végpontjai."""
    portal = _get_portal_or_404(db, portal_id)
    if payload.folder_id is not None:
        folder = db.get(PortalFolder, payload.folder_id)
        if folder is None or folder.portal_id != portal.id:
            raise HTTPException(status_code=404, detail="Ez a mappa nem ehhez a portálhoz tartozik.")
    portal.feltolto_token = uuid.uuid4().hex
    portal.feltolto_folder_id = payload.folder_id
    db.commit()
    return PortalShareLink(token=portal.feltolto_token, url=f"{_portal_front()}/feltoltes/{portal.feltolto_token}")


@router.delete("/{portal_id}/feltolto-link", status_code=204)
def feltolto_link_visszavonas(
    portal_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    portal = _get_portal_or_404(db, portal_id)
    portal.feltolto_token = None
    portal.feltolto_folder_id = None
    db.commit()


@router.post("/folders/{folder_id}/share-link", response_model=PortalShareLink)
def folder_share_link(
    folder_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """EGY MAPPA megosztása linkkel - a link birtokosa csak ezt a mappát látja
    (lásd routes/portal_public.megosztas)."""
    folder = db.get(PortalFolder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="A mappa nem található.")
    if not folder.share_token:
        folder.share_token = uuid.uuid4().hex
        db.commit()
    return PortalShareLink(token=folder.share_token, url=f"{_portal_front()}/megosztas/{folder.share_token}")


@router.delete("/folders/{folder_id}/share-link", status_code=204)
def folder_share_link_visszavonas(
    folder_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    folder = db.get(PortalFolder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="A mappa nem található.")
    folder.share_token = None
    db.commit()


@router.post("/videos/{video_id}/share-link", response_model=PortalShareLink)
def video_share_link(
    video_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """EGY VIDEÓ megosztása linkkel - a link birtokosa csak ezt az egy videót
    látja."""
    video = db.get(PortalVideo, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="A videó nem található.")
    if not video.share_token:
        video.share_token = uuid.uuid4().hex
        db.commit()
    return PortalShareLink(token=video.share_token, url=f"{_portal_front()}/megosztas/{video.share_token}")


@router.delete("/videos/{video_id}/share-link", status_code=204)
def video_share_link_visszavonas(
    video_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    video = db.get(PortalVideo, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="A videó nem található.")
    video.share_token = None
    db.commit()


# ---------------- Videók ----------------


class MultipartInitIn(BaseModel):
    filename: str
    content_type: str = "video/mp4"
    title: str | None = None


class MultipartPartIn(BaseModel):
    upload_id: str
    key: str
    part_number: int


class MultipartCompleteIn(BaseModel):
    upload_id: str
    key: str
    video_id: int
    parts: list[dict]


class MultipartAbortIn(BaseModel):
    upload_id: str
    key: str
    video_id: int


@router.post("/{portal_id}/videos/multipart/init")
def multipart_init(
    portal_id: int,
    payload: MultipartInitIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """Nagy videók feltöltéséhez - a kliens (admin UI) ezt hívja először,
    majd a kapott upload_id-vel darabolva, közvetlenül R2-be tölt fel
    (lásd sign-part), és a végén complete-tel zárja le. Ez ad valós
    feltöltési haladásjelzést, szemben az egyszerű /videos POST-tal."""
    portal = _get_portal_or_404(db, portal_id)
    max_order = max([v.sort_order for v in portal.videos], default=-1)
    video = PortalVideo(
        portal_id=portal_id,
        title=payload.title or os.path.splitext(payload.filename)[0],
        status="uploading",
        sort_order=max_order + 1,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    key = f"videos/{video.id}/upload.mp4"
    upload_id = storage.create_multipart(key, payload.content_type)
    video.source_key = key
    db.commit()

    return {"video_id": video.id, "upload_id": upload_id, "key": key}


@router.post("/videos/multipart/sign-part")
def multipart_sign_part(payload: MultipartPartIn, _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR))):
    return {"url": storage.presigned_part(payload.key, payload.upload_id, payload.part_number)}


@router.post("/videos/multipart/complete", response_model=PortalVideoOut)
def multipart_complete(
    payload: MultipartCompleteIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    video = db.get(PortalVideo, payload.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Videó nem található")
    storage.complete_multipart(payload.key, payload.upload_id, payload.parts)
    video.status = "processing"
    db.commit()
    db.refresh(video)
    _enqueue_processing(video.id, payload.key)
    return PortalVideoOut.model_validate(video)


@router.post("/videos/multipart/abort")
def multipart_abort(
    payload: MultipartAbortIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    storage.abort_multipart(payload.key, payload.upload_id)
    video = db.get(PortalVideo, payload.video_id)
    if video:
        db.delete(video)
        db.commit()
    return {"ok": True}


@router.post("/{portal_id}/videos", response_model=PortalVideoOut)
async def upload_video(
    portal_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    portal = _get_portal_or_404(db, portal_id)
    max_order = max([v.sort_order for v in portal.videos], default=-1)
    video = PortalVideo(
        portal_id=portal_id,
        title=title or os.path.splitext(file.filename or "Untitled")[0],
        status="processing",
        sort_order=max_order + 1,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    source_key = f"videos/{video.id}/upload.mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    storage.upload_file(tmp_path, source_key, "video/mp4")
    os.unlink(tmp_path)
    video.source_key = source_key
    db.commit()
    db.refresh(video)

    _enqueue_processing(video.id, source_key)
    return PortalVideoOut.model_validate(video)


@router.get("/videos/{video_id}/download-url")
def video_download_url(
    video_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    video = db.get(PortalVideo, video_id)
    if not video or not video.source_key:
        raise HTTPException(status_code=404, detail="Nem található")
    safe = (video.title or "video").replace('"', "")
    return {"url": storage.presigned_download(video.source_key, f"{safe}.mp4")}


@router.patch("/videos/{video_id}", response_model=PortalVideoOut)
def update_video(
    video_id: int,
    payload: PortalVideoUpdate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    video = db.get(PortalVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Nem található")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(video, k, v)
    db.commit()
    return PortalVideoOut.model_validate(video)


@router.post("/videos/{video_id}/replace", response_model=PortalVideoOut)
async def replace_video(
    video_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    video = db.get(PortalVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Nem található")
    storage.delete_prefix(f"videos/{video.id}")
    video.status = "processing"
    source_key = f"videos/{video.id}/upload.mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    storage.upload_file(tmp_path, source_key, "video/mp4")
    os.unlink(tmp_path)
    video.source_key = source_key
    db.commit()
    _enqueue_processing(video.id, source_key)
    return PortalVideoOut.model_validate(video)


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(
    video_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR))
):
    video = db.get(PortalVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Nem található")
    storage.delete_prefix(f"videos/{video.id}")
    db.delete(video)
    db.commit()


@router.post("/{portal_id}/videos/reorder")
def reorder_videos(
    portal_id: int,
    payload: ReorderPayload,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    for index, vid in enumerate(payload.ordered_ids):
        video = db.get(PortalVideo, vid)
        if video and video.portal_id == portal_id:
            video.sort_order = index
    db.commit()
    return {"ok": True}


# ---------------- Mappák ----------------


@router.post("/{portal_id}/folders", response_model=PortalFolderOut)
def create_folder(
    portal_id: int,
    payload: PortalFolderCreate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    portal = _get_portal_or_404(db, portal_id)
    max_order = max([f.sort_order for f in portal.folders], default=-1)
    folder = PortalFolder(portal_id=portal_id, name=payload.name, sort_order=max_order + 1)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return PortalFolderOut.model_validate(folder)


@router.patch("/folders/{folder_id}", response_model=PortalFolderOut)
def update_folder(
    folder_id: int,
    payload: PortalFolderUpdate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    folder = db.get(PortalFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Nem található")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(folder, k, v)
    db.commit()
    return PortalFolderOut.model_validate(folder)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(
    folder_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR))
):
    folder = db.get(PortalFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Nem található")
    for v in list(folder.videos):
        storage.delete_prefix(f"videos/{v.id}")
        db.delete(v)
    for img in list(folder.images):
        storage.delete_prefix(f"images/{img.id}")
        db.delete(img)
    db.delete(folder)
    db.commit()


# ---------------- Képek ----------------


@router.post("/{portal_id}/images", response_model=PortalImageOut)
async def upload_image(
    portal_id: int,
    file: UploadFile = File(...),
    folder_id: int | None = Form(None),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    portal = _get_portal_or_404(db, portal_id)
    image = PortalImage(portal_id=portal_id, folder_id=folder_id)
    db.add(image)
    db.flush()

    data = await file.read()
    ext = (file.filename or "image.jpg").split(".")[-1].lower()
    key = f"images/{image.id}/original.{ext}"
    storage.upload_bytes(data, key, file.content_type or "image/jpeg")

    thumb_url = ""
    try:
        img = PILImage.open(io.BytesIO(data))
        img = img.convert("RGB")
        img.thumbnail((1200, 1200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=True)
        thumb_key = f"images/{image.id}/thumb.jpg"
        storage.upload_bytes(buf.getvalue(), thumb_key, "image/jpeg")
        thumb_url = storage.public_url(thumb_key)
    except Exception:
        thumb_url = ""

    max_order = max([i.sort_order for i in portal.images], default=-1)
    image.title = (file.filename or "").rsplit(".", 1)[0]
    image.url = storage.public_url(key)
    image.thumbnail_url = thumb_url
    image.key = key
    image.size_bytes = len(data)
    image.sort_order = max_order + 1
    db.commit()
    db.refresh(image)
    return PortalImageOut.model_validate(image)


@router.patch("/images/{image_id}", response_model=PortalImageOut)
def update_image(
    image_id: int,
    payload: PortalImageUpdate,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    image = db.get(PortalImage, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Nem található")
    if payload.set_folder:
        image.folder_id = payload.folder_id
    if payload.title is not None:
        image.title = payload.title
    db.commit()
    db.refresh(image)
    return PortalImageOut.model_validate(image)


@router.delete("/images/{image_id}", status_code=204)
def delete_image(
    image_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR))
):
    image = db.get(PortalImage, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Nem található")
    storage.delete_prefix(f"images/{image.id}")
    db.delete(image)
    db.commit()


# ---------------- Notion + karbantartás ----------------


@router.post("/notion/sync")
def notion_sync(db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR))):
    return portal_notion.sync_portals(db)


@router.post("/maintenance/backfill-video-sizes")
def backfill_video_sizes(
    db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR))
):
    videos = db.query(PortalVideo).all()
    updated = skipped = 0
    errors: list[str] = []
    for v in videos:
        if v.size_bytes and v.size_bytes > 0:
            skipped += 1
            continue
        if not v.source_key:
            skipped += 1
            continue
        try:
            size = storage.head_size(v.source_key)
            if size > 0:
                v.size_bytes = size
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append(f"{v.id}: {e}")
            skipped += 1
    db.commit()
    return {"updated": updated, "skipped": skipped, "total": len(videos), "errors": errors[:5]}


@router.get("/maintenance/pending-deletion")
def pending_deletion(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """A 90+ napja lejárt FIZETŐS portálok, amelyek anyagai törölhetők."""
    now = datetime.now()
    result = []
    for p in db.query(Portal).all():
        if p.payment_mode != "paid" or not p.expires_at:
            continue
        deadline = p.expires_at + timedelta(days=90)
        if now.date() > deadline:
            video_count, image_count = len(p.videos), len(p.images)
            if video_count == 0 and image_count == 0:
                continue
            result.append(
                {
                    "id": p.id,
                    "title": resolve_title(p),
                    "client_name": resolve_client_name(p),
                    "expires_at": str(p.expires_at),
                    "video_count": video_count,
                    "image_count": image_count,
                }
            )
    return result


@router.post("/maintenance/{portal_id}/purge-files")
def purge_portal_files(
    portal_id: int, db: Session = Depends(get_db), _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR))
):
    """Egy portál ÖSSZES fájlját törli az R2-ből (videók + képek), de a
    PORTÁLT meghagyja (hogy a kapcsolat-oldal továbbra is működjön)."""
    portal = _get_portal_or_404(db, portal_id)
    for v in list(portal.videos):
        storage.delete_prefix(f"videos/{v.id}")
        db.delete(v)
    for img in list(portal.images):
        storage.delete_prefix(f"images/{img.id}")
        db.delete(img)
    db.commit()
    return {"ok": True, "purged": True}
