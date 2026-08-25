from datetime import date, datetime

from pydantic import BaseModel


class DocumentAttachmentRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    kategoria: str
    filename: str
    url: str
    content_type: str | None = None
    meret_bajt: int | None = None
    created_at: datetime
    #: Csak "szamla" kategóriánál értelmezett - lásd models/document_attachment.py.
    fizetesi_hatarido: date | None = None
    kifizetve_datuma: date | None = None

    model_config = {"from_attributes": True}


class DocumentAttachmentFizetesIn(BaseModel):
    """A számla-fájl fizetési állapota - mindkét mező mindig együtt megy, hogy
    egy határidő törlése (null) is kifejezhető legyen, ne csak a beállítása."""

    fizetesi_hatarido: date | None = None
    kifizetve_datuma: date | None = None
