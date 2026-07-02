from pydantic import BaseModel


class FolderBase(BaseModel):
    nev: str
    project_id: int
    sort_order: int = 0


class FolderCreate(FolderBase):
    pass


class FolderUpdate(BaseModel):
    nev: str | None = None
    sort_order: int | None = None


class FolderRead(FolderBase):
    id: int

    model_config = {"from_attributes": True}


class MediaBase(BaseModel):
    title: str
    project_id: int
    folder_id: int | None = None
    storage_key: str
    thumbnail_url: str | None = None
    duration_seconds: int | None = None
    resolution_label: str | None = None
    size_bytes: int | None = None
    status: str = "processing"


class MediaCreate(MediaBase):
    pass


class MediaUpdate(BaseModel):
    folder_id: int | None = None
    thumbnail_url: str | None = None
    status: str | None = None


class MediaRead(MediaBase):
    id: int

    model_config = {"from_attributes": True}
