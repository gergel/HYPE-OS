from datetime import date

from sqlalchemy import Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class DocumentAttachment(TimestampMixin, Base):
    """Egy tetszőleges rekordhoz (szerződéshez, projektkódhoz, kiadáshoz…)
    csatolt fájl - MINDIG az R2 tárhelyen (lásd services/document_storage.py),
    soha nem a szolgáltatás lemezén: a Railway konténer fájlrendszere
    minden újraindításnál/deploynál elveszik.

    Szándékosan generikus (entity_type + entity_id), nem entitásonként külön
    tábla és külön oszlopok: a szerződések, TIG-ek és számlák ugyanazt a
    "van egy PDF, nézd meg / töltsd le / töröld" viselkedést kívánják, és így
    egyetlen végpont (routes/attachments.py) és egyetlen frontend komponens
    (DokumentumFeltoltes) szolgálja ki mindet. Az entity_type az API-kulcsokat
    használja (lásd services/entity_registry.py ENTITY_MODELS), hogy a
    frontend ugyanazzal a névvel hivatkozzon rájuk, mint mindenhol máshol.
    """

    __tablename__ = "document_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)

    # Mi ez a fájl: "szerzodes", "tig", "szamla" vagy "egyeb" (lásd
    # services/attachments.py KATEGORIAK). A havi számla-csomag és a
    # papírozás-nézetek ez alapján tudják, mit keresnek.
    kategoria: Mapped[str] = mapped_column(String(30), nullable=False, default="egyeb")

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Az R2 objektumkulcs (nem csak a publikus URL) - enélkül törléskor és a
    # havi számla-ZIP összeállításakor nem tudnánk visszafejteni, melyik
    # objektumot kell a tárhelyről elővenni.
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    meret_bajt: Mapped[int | None] = mapped_column()

    # Ha a fájl Notion importból származik: az EREDETI Notion fájl-útvonala
    # (aláírás/query nélkül). Ez teszi idempotenssé az importot - egy újabb
    # futás ugyanazt a fájlt nem tölti le és nem duplikálja (lásd
    # notion_import/files.py).
    notion_forras: Mapped[str | None] = mapped_column(String(700))

    # CSAK "szamla" kategóriánál értelmezett: melyik feltöltött számlának
    # mikor jár le a fizetési határideje, és mikor (ha egyáltalán) fizették
    # ki - egyénileg PER FÁJL, mert egy projektkódhoz több számla is
    # tartozhat (osztott számlázás), és azok külön-külön esedékesek/
    # kifizetettek lehetnek (lásd routes/attachments.py PUT
    # .../fizetesi-allapot). `kifizetve_datuma` hiánya = még nincs kifizetve.
    fizetesi_hatarido: Mapped[date | None] = mapped_column(Date)
    kifizetve_datuma: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        Index("ix_document_attachments_entity", "entity_type", "entity_id"),
        Index("ix_document_attachments_notion_forras", "notion_forras"),
    )
