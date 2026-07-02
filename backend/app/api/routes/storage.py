"""Storage modul: Media (feltöltött videó/kép) + Folder - Cloudflare R2 felett."""

from app.api.crud_router import build_crud_router
from app.models.media import Folder, Media
from app.schemas.media import FolderCreate, FolderRead, FolderUpdate, MediaCreate, MediaRead, MediaUpdate

folders_router = build_crud_router(
    model=Folder,
    create_schema=FolderCreate,
    update_schema=FolderUpdate,
    read_schema=FolderRead,
    prefix="/folders",
    tags=["storage"],
)

media_router = build_crud_router(
    model=Media,
    create_schema=MediaCreate,
    update_schema=MediaUpdate,
    read_schema=MediaRead,
    prefix="/media",
    tags=["storage"],
)
