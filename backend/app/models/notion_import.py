from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class NotionImportMap(TimestampMixin, Base):
    """Notion page ID -> HYPE OS entitás leképezés. Ez teszi idempotenssé az importot
    (docs/hype_os_build_roadmap.md Fázis 2 elvárása): újrafuttatáskor egy már látott
    Notion page-hez tartozó rekordot frissítünk, nem duplikálunk - és ez oldja fel a
    Notion relation mezőket (page ID -> a mi integer FK-nk) is."""

    __tablename__ = "notion_import_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    notion_page_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(nullable=False)
