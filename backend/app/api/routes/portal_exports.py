"""Export access follows the deployed portal's password/share/hidden-item rules."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.portal import Portal, PortalFolder, PortalVideo
from app.models.portal_export import PortalExport
from app.api.routes.portal_public import get_public_portal, get_by_share, megosztas, _is_expired
from app.services.portal_exports import make_manifest, request_export, now, object_store, current_sources

router = APIRouter(prefix='/public/portal-exports', tags=['portal-exports'])

class Access(BaseModel):
    slug: str = Field(default='', max_length=120)
    authorization: str | None = None
    belsos_token: str | None = None
    share: str | None = None
    part: str | None = None

class Item(BaseModel):
    id: int
    folder: str | None = Field(default=None, max_length=500)

class ExportRequest(BaseModel):
    access: Access
    images: list[Item] = Field(default_factory=list, max_length=20000)
    videos: list[Item] = Field(default_factory=list, max_length=20000)
    filename: str = Field(default='anyagok', max_length=200)


def allowed(db, access):
    if access.part:
        data = megosztas(access.part, db)
    elif access.share:
        data = get_by_share(access.share, db)
    elif access.slug:
        data = get_public_portal(access.slug, db, access.authorization, access.belsos_token)
    else:
        raise HTTPException(401, 'Nyisd meg újra a portált.')
    if data.get('locked'):
        raise HTTPException(401, 'A portál jelszava szükséges.')
    if data.get('expired'):
        raise HTTPException(410, 'A portál lejárt.')
    view = data.get('project')
    if not view:
        raise HTTPException(404, 'A portál nem található.')
    portal = db.scalar(select(Portal).where(Portal.slug == view['slug']))
    if not portal or portal.status != 'live' or _is_expired(portal):
        raise HTTPException(410, 'A portál nem elérhető.')
    return portal, {i['id'] for i in view['images']}, {v['id'] for v in view['videos']}


def status(job):
    return dict(id=job.id, state=job.state, bytes_done=job.bytes_done,
        total_bytes=job.total_bytes, error=job.error, expires_at=job.expires_at,
        file_count=len(job.manifest), size=job.object_size)

@router.post('')
def create(payload: ExportRequest, db: Session = Depends(get_db)):
    portal, images, videos = allowed(db, payload.access)
    if not payload.images and not payload.videos:
        raise HTTPException(400, 'Nincs letölthető fájl.')
    if not {i.id for i in payload.images} <= images or not {v.id for v in payload.videos} <= videos:
        raise HTTPException(404, 'A kijelölt fájl nem elérhető.')
    try:
        manifest = make_manifest(db, payload.images, payload.videos)
        job = request_export(db, portal.id, manifest, payload.filename)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return status(job)

@router.post('/{job_id}/status')
def check(job_id: str, access: Access, db: Session = Depends(get_db)):
    portal, images, videos = allowed(db, access)
    job = db.get(PortalExport, job_id)
    if not job or job.portal_id != portal.id or any(
        e['id'] not in (images if e['kind'] == 'image' else videos) for e in job.manifest):
        raise HTTPException(404, 'A csomag nem elérhető.')
    result = status(job)
    if job.state == 'ready':
        if not job.expires_at or job.expires_at <= now():
            result['state'] = 'expired'
        else:
            try:
                current_sources(db, job.manifest)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            # Each link is renewed on demand and points to the same immutable object.
            result['url'] = object_store().presigned_download_url(job.object_key,
                expires_in=3600, filename=job.filename)
    return result
