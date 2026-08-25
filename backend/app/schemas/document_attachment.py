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
    netto: float | None = None
    plusz_afa: bool | None = None
    bevetelbe_ne_keruljon: bool = False
    bevetel_kihagyas_oka: str | None = None

    model_config = {"from_attributes": True}


class DocumentAttachmentHataridoIn(BaseModel):
    """A számla-fájl fizetési határideje. Kizárólag ez - a kifizetés jelölése
    a POST .../kifizetve végponton megy, mert az bevétel-sort is nyit."""

    fizetesi_hatarido: date | None = None


class DocumentAttachmentKifizetesIn(BaseModel):
    """Egy konkrét feltöltött számla kifizetettnek jelölése - lásd
    services/megrendeloi_szamla.jelold_szamlat_kifizetettnek."""

    #: MIKOR érkezett meg a pénz. Kötelező - ebből lesz a bevétel-sor napja.
    kifizetes_datuma: date
    #: Ennek a SZÁMLÁNAK a nettó összege. Osztott számlázásnál (több számla
    #: egy projektkódon) kötelező - egyetlen számlánál elhagyható, ilyenkor a
    #: projektkód vállalási ára adja az összeget.
    netto: float | None = None
    plusz_afa: bool = False
    fizetes_modja: str | None = None
    #: "Kifizetve, de ne kerüljön a bevételek közé" - indok kell hozzá.
    bevetelbe_ne_keruljon: bool = False
    kihagyas_oka: str | None = None
