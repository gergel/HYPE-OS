from datetime import datetime

from sqlalchemy import JSON, DateTime, String
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
    # 36 karakter épp elég egy valódi Notion UUID-hoz, de a szintetikus kulcsaink
    # (pl. "client:cegnev-vagy-email@pelda.hu" az Ügyfél cég-csoportosításnál) ennél
    # hosszabbak is lehetnek - bőven méretezve, hogy ne csorduljon túl.
    notion_page_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(nullable=False)

    #: Amit a LEGUTÓBBI import ténylegesen beírt ebbe a rekordba, mezőnként egy
    #: normalizált szöveges érték. Ez a "referenciapont", amihez képest el
    #: tudjuk dönteni, hogy egy mezőt azóta helyben átírtak-e: ha a mostani
    #: adatbázis-érték megegyezik ezzel, senki nem nyúlt hozzá, tehát a Notion
    #: frissítése nyugodtan felülírhatja; ha eltér, akkor helyben módosították,
    #: és az import NEM írja felül (lásd notion_import/engine.py).
    #:
    #: Enélkül egy újrafuttatott import visszaírná a Notion (elavult) értékét
    #: mindarra, amit a HYPE OS-ben már befejeztek - például egy itt megírt és
    #: kiküldött TIG adatait.
    imported_fields: Mapped[dict | None] = mapped_column(JSON)
    #: Mikor futott le utoljára az import erre a rekordra.
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
