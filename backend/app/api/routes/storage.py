"""Storage modul: Media (feltöltött videó/kép) + Folder - privát objektumtár felett.

A média- és mappalisták **nem nyilvánosak**: az olvasás is belsős szerepkört kér.
Az ügyfél a saját galériáját a jogosultság-ellenőrzött galéria-export API-n
keresztül éri el (``/api/v1/projects/{id}/gallery-export``).
"""

from app.api.crud_router import build_crud_router
from app.core.security import Role
from app.models.media import Folder, Media
from app.schemas.media import FolderCreate, FolderRead, FolderUpdate, MediaCreate, MediaRead, MediaUpdate

folders_router = build_crud_router(
    model=Folder,
    create_schema=FolderCreate,
    update_schema=FolderUpdate,
    read_schema=FolderRead,
    prefix="/folders",
    tags=["storage"],
    read_roles=(Role.ADMIN, Role.OPERATOR, Role.VAGO),
)

media_router = build_crud_router(
    model=Media,
    create_schema=MediaCreate,
    update_schema=MediaUpdate,
    read_schema=MediaRead,
    prefix="/media",
    tags=["storage"],
    read_roles=(Role.ADMIN, Role.OPERATOR, Role.VAGO),
)
