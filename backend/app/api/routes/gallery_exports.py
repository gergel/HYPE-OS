"""Galéria-export API.

Jogosultság-ellenőrzés **három** ponton történik, egymástól függetlenül:

1. job létrehozásakor (``POST .../gallery-export``),
2. job lekérdezésekor (``GET /gallery-exports/...``),
3. a letöltési link kiadásakor **és** a link beváltásakor is.

Idegen bérlő (Client) adatára 404 a válasz, nem 403 - így az sem derül ki, hogy
az adott projekt/export egyáltalán létezik-e.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee, SystemRole
from app.models.gallery_export import ExportStatus, GalleryExportJob
from app.schemas.gallery_export import (
    DownloadTicketRead,
    GalleryExportRead,
    GalleryExportStateRead,
    GalleryPlanRead,
)
from app.services.gallery_export import (
    CREATE_ROLES,
    INTERNAL_ROLES,
    GalleryExportError,
    assert_job_visible,
    current_job_for_project,
    get_or_create_job,
    get_project_for_user,
    issue_download_ticket,
    parse_download_token,
    plan_gallery,
    utcnow,
)
from app.services.storage import ObjectNotFound, get_storage
from app.services.storage.s3 import content_disposition

router = APIRouter(tags=["gallery-export"])

_STATUS_BY_CODE = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "invalid_token": status.HTTP_403_FORBIDDEN,
    "expired_token": status.HTTP_410_GONE,
    "expired": status.HTTP_410_GONE,
    "not_ready": status.HTTP_409_CONFLICT,
    "empty_gallery": status.HTTP_409_CONFLICT,
    "too_many_files": status.HTTP_409_CONFLICT,
    "source_missing": status.HTTP_409_CONFLICT,
}


def _http(error: GalleryExportError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": error.code, "message": error.message},
    )


def _base_url(request: Request) -> str:
    parts = urlsplit(str(request.base_url))
    return f"{parts.scheme}://{parts.netloc}"


def _load_job(db: Session, public_id: str, user: Employee) -> GalleryExportJob:
    job = db.scalars(
        select(GalleryExportJob).where(GalleryExportJob.public_id == public_id)
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Az export nem található."})
    try:
        assert_job_visible(db, job, user)
    except GalleryExportError as exc:
        raise _http(exc) from exc
    return job


# --- projekt-szintű végpontok ------------------------------------------------


@router.post(
    "/projects/{project_id}/gallery-export",
    response_model=GalleryExportRead,
    summary="Galéria ZIP64 export indítása (idempotens)",
)
def create_gallery_export(
    project_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Idempotens: ugyanarra a galéria-verzióra kétszer kattintva ugyanaz a job jön vissza."""
    if current_user.role not in CREATE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Nincs jogosultságod."})
    try:
        project = get_project_for_user(db, project_id, current_user)
        job, created = get_or_create_job(db, project, current_user, storage=get_storage())
    except GalleryExportError as exc:
        raise _http(exc) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return job


@router.get(
    "/projects/{project_id}/gallery-export",
    response_model=GalleryExportStateRead,
    summary="A galéria aktuális verziója és a hozzá tartozó job",
)
def get_gallery_export_state(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Az oldal újranyitásakor ez adja vissza a futó/kész jobot - kliensoldali tárolás nélkül."""
    try:
        project = get_project_for_user(db, project_id, current_user)
    except GalleryExportError as exc:
        raise _http(exc) from exc
    storage = get_storage()
    try:
        plan = plan_gallery(db, project, storage=storage)
    except GalleryExportError as exc:
        return GalleryExportStateRead(unavailable_reason=exc.message)
    job = current_job_for_project(db, project, storage=storage)
    return GalleryExportStateRead(
        plan=GalleryPlanRead(
            project_id=project.id,
            source_fingerprint=plan.fingerprint,
            file_count=plan.file_count,
            total_source_bytes=plan.total_source_bytes,
            expected_archive_bytes=plan.expected_archive_bytes,
        ),
        job=GalleryExportRead.model_validate(job) if job is not None else None,
    )


# --- job-szintű végpontok ----------------------------------------------------


@router.get("/gallery-exports", response_model=list[GalleryExportRead], summary="Saját exportok")
def list_gallery_exports(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    query = select(GalleryExportJob).order_by(GalleryExportJob.id.desc())
    if current_user.role not in INTERNAL_ROLES:
        if current_user.role is not SystemRole.UGYFEL or current_user.client_id is None:
            return []
        query = query.where(GalleryExportJob.client_id == current_user.client_id)
    return list(db.scalars(query.offset(skip).limit(limit)))


@router.get("/gallery-exports/{public_id}", response_model=GalleryExportRead, summary="Export állapota")
def get_gallery_export(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    job = _load_job(db, public_id, current_user)
    if job.status is ExportStatus.READY and job.expires_at and job.expires_at <= utcnow():
        job.status = ExportStatus.EXPIRED
        db.commit()
        db.refresh(job)
    return job


@router.post(
    "/gallery-exports/{public_id}/download-url",
    response_model=DownloadTicketRead,
    summary="Letöltési URL kiadása / megújítása",
)
def create_download_url(
    public_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Lejárt link esetén ugyanezt kell újra hívni: az objektum változatlan, a
    letöltés Range-dzsel folytatható onnan, ahol megszakadt."""
    job = _load_job(db, public_id, current_user)
    try:
        ticket = issue_download_ticket(db, job, current_user, get_storage(), base_url=_base_url(request))
    except GalleryExportError as exc:
        raise _http(exc) from exc
    return ticket


# --- Range-képes letöltés (lokális/privát backend) ---------------------------

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, size: int) -> tuple[int, int] | None:
    """Egyetlen bájt-tartomány feldolgozása. ``None`` = teljes fájl."""
    header = header.strip()
    if "," in header:  # több tartomány: a teljes fájlt adjuk (RFC szerint megengedett)
        return None
    match = _RANGE_RE.match(header)
    if not match:
        return None
    start_raw, end_raw = match.groups()
    if not start_raw and not end_raw:
        return None
    if not start_raw:  # bytes=-N -> az utolsó N bájt
        length = int(end_raw)
        if length <= 0:
            raise ValueError("unsatisfiable")
        start = max(size - length, 0)
        end = size - 1
    else:
        start = int(start_raw)
        end = int(end_raw) if end_raw else size - 1
        if start >= size or end < start:
            raise ValueError("unsatisfiable")
        end = min(end, size - 1)
    return start, end


@router.get(
    "/gallery-exports/{public_id}/download",
    summary="Csomag letöltése (HTTP Range támogatással)",
)
@router.head("/gallery-exports/{public_id}/download", include_in_schema=False)
def download_gallery_export(
    public_id: str,
    request: Request,
    token: str = Query(..., description="A /download-url végponton kapott aláírt jegy"),
    db: Session = Depends(get_db),
):
    """A jegy aláírt és lejáró, de a jogosultságot **itt is** újraellenőrizzük az
    adatbázisból - visszavont hozzáférés esetén a régi link sem működik."""
    try:
        token_public_id, user_id, _exp = parse_download_token(token)
    except GalleryExportError as exc:
        raise _http(exc) from exc
    if token_public_id != public_id:
        raise HTTPException(status_code=403, detail={"code": "invalid_token", "message": "Érvénytelen letöltési link."})

    user = db.get(Employee, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "A felhasználó nem aktív."})

    job = db.scalars(select(GalleryExportJob).where(GalleryExportJob.public_id == public_id)).first()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Az export nem található."})
    try:
        assert_job_visible(db, job, user)
    except GalleryExportError as exc:
        raise _http(exc) from exc

    if job.status is not ExportStatus.READY or not job.object_key:
        raise HTTPException(status_code=409, detail={"code": "not_ready", "message": "A csomag nem érhető el."})
    if job.expires_at and job.expires_at <= utcnow():
        job.status = ExportStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=410, detail={"code": "expired", "message": "A csomag lejárt."})

    storage = get_storage()
    try:
        stored = storage.stat(job.object_key)
    except ObjectNotFound as exc:
        raise HTTPException(status_code=410, detail={"code": "expired", "message": "A csomag már nem érhető el."}) from exc

    size = stored.size
    etag = f'"{job.archive_sha256 or stored.etag}"'
    filename = job.filename or f"{public_id}.zip"
    headers = {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Content-Disposition": content_disposition(filename),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }

    range_header = request.headers.get("range")
    if_range = request.headers.get("if-range")
    #: Ha az If-Range nem az aktuális ETag, a tartomány-kérés teljes választ kap.
    if range_header and if_range and if_range.strip() != etag:
        range_header = None

    byte_range = None
    if range_header:
        try:
            byte_range = _parse_range(range_header, size)
        except ValueError:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={**headers, "Content-Range": f"bytes */{size}"},
            )

    if byte_range is None:
        start, end, code = 0, size - 1, status.HTTP_200_OK
    else:
        start, end = byte_range
        code = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    length = max(end - start + 1, 0)
    headers["Content-Length"] = str(length)

    if request.method == "HEAD":
        return Response(status_code=code, headers=headers, media_type="application/zip")

    return StreamingResponse(
        storage.read_stream(job.object_key, offset=start, length=length,
                            chunk_size=settings.export_chunk_bytes),
        status_code=code,
        headers=headers,
        media_type="application/zip",
    )
