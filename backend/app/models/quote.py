"""Árajánlat-készítő modul (2026-09): tétel-katalógus, sablonok, ajánlatok.

A felhasználó specifikációja (HYPE_OS_arajanlat_keszito_PROMPT.md) szerint:
sablonból vagy üresen induló ajánlat, a katalógusból egy kattintással hozzáadott
tételek, minden átírható, és XLSX / PDF export a megszokott HYPE-formában.

Eltérések a specifikációtól a repó konvenciói miatt (lásd
docs/arajanlat-keszito.md): nincs külön Postgres-séma (a repó egy sémát
használ) - a táblák `quote_` előtaggal élnek; az enumok szöveges oszlopok
CHECK-kényszerrel; az ügyfél a meglévő `clients` tábla.

PÉNZ: egész forint (BIGINT), NETTÓ - float soha. Az ÁFA csak kijelzés.

A korábbi, JSON-alapú szerkesztő táblái (`arajanlatok`, `arajanlat_tetelek`)
érintetlenül maradnak; a régi ajánlatok a felületen továbbra is megnyithatók."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

EGYSEGEK = ("fo_nap", "db_nap", "nap", "ora", "alkalom", "db", "project", "km", "fo", "honap")
BRANDEK = ("HYPE", "CB")
STATUSZOK = ("draft", "sent", "accepted", "rejected", "archived")
ARAZASI_MODOK = ("one_off", "monthly")


def _enum_check(oszlop: str, ertekek: tuple[str, ...], nev: str) -> CheckConstraint:
    return CheckConstraint(f"{oszlop} IN ({', '.join(repr(e) for e in ertekek)})", name=nev)


class QuoteCatalogCategory(Base):
    __tablename__ = "quote_catalog_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QuoteCatalogItem(Base):
    """Katalógus-tétel. Az alapár a kattintáskor BEMÁSOLÓDIK az ajánlatba
    (ár-snapshot) - a későbbi átárazás a meglévő ajánlatokat nem írja át."""

    __tablename__ = "quote_catalog_items"
    __table_args__ = (_enum_check("unit", EGYSEGEK, "ck_quote_catalog_items_unit"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("quote_catalog_categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="db")
    base_price: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    #: Tájékoztató ársáv a korábbi ajánlatokból - a számításban nem vesz részt.
    price_min: Mapped[int | None] = mapped_column(BigInteger)
    price_max: Mapped[int | None] = mapped_column(BigInteger)
    price_median: Mapped[int | None] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Címkék; a `variant:<csoport>` címkéjű tételek egymásra cserélhetők
    #: (pl. a 15 m²-es LED fal P4.8 / P3.9 / P2.5 változata).
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: A seed stabil kulcsa (pl. "c063") - az újrafuttatás ez alapján ismeri fel.
    seed_key: Mapped[str | None] = mapped_column(String(20), unique=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))

    category: Mapped[QuoteCatalogCategory] = relationship()


class QuoteCatalogPriceHistory(Base):
    __tablename__ = "quote_catalog_price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("quote_catalog_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_price: Mapped[int | None] = mapped_column(BigInteger)
    new_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))


class QuoteNotePreset(TimestampMixin, Base):
    """Megjegyzés-sablon (pl. standard HYPE, angol, ContentBee)."""

    __tablename__ = "quote_note_presets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QuoteTemplate(TimestampMixin, Base):
    __tablename__ = "quote_templates"
    __table_args__ = (
        _enum_check("brand", BRANDEK, "ck_quote_templates_brand"),
        _enum_check("pricing_mode", ARAZASI_MODOK, "ck_quote_templates_pricing_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str] = mapped_column(String(10), nullable=False, default="HYPE")
    pricing_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="one_off")
    #: Az összesítő sor címkéje (pl. „STREAMING SZOLGÁLTATÁS KÖLTSÉGE”).
    summary_label: Mapped[str | None] = mapped_column(String(120))
    #: Az „Alkalom” oszlop felirata a szerkesztőben (pl. LED falnál „Nap”).
    occasions_label: Mapped[str | None] = mapped_column(String(40))
    #: Tájékoztató tipikus végösszeg a sablon-kártyán (korábbi ajánlatok mediánja).
    typical_total: Mapped[int | None] = mapped_column(BigInteger)
    default_note_id: Mapped[int | None] = mapped_column(ForeignKey("quote_note_presets.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seed_key: Mapped[str | None] = mapped_column(String(20), unique=True)

    items: Mapped[list[QuoteTemplateItem]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="QuoteTemplateItem.sort_order"
    )


class QuoteTemplateItem(Base):
    __tablename__ = "quote_template_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("quote_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: None: egyedi sor (a név / leírás / ár a sablonban áll).
    catalog_item_id: Mapped[int | None] = mapped_column(ForeignKey("quote_catalog_items.id", ondelete="SET NULL"))
    section: Mapped[str | None] = mapped_column(String(120))
    name_override: Mapped[str | None] = mapped_column(String(255))
    description_override: Mapped[str | None] = mapped_column(Text)
    unit_override: Mapped[str | None] = mapped_column(String(20))
    default_occasions: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    default_quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    price_override: Mapped[int | None] = mapped_column(BigInteger)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template: Mapped[QuoteTemplate] = relationship(back_populates="items")
    catalog_item: Mapped[QuoteCatalogItem | None] = relationship()


class QuoteNumberCounter(Base):
    """Évente újrainduló sorszám márkánként (HYPE-2026-0001, CB-2026-0001) -
    soronként zárolva adjuk ki, így párhuzamos létrehozásnál sem ütközik."""

    __tablename__ = "quote_number_counters"

    brand: Mapped[str] = mapped_column(String(10), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        _enum_check("brand", BRANDEK, "ck_quotes_brand"),
        _enum_check("status", STATUSZOK, "ck_quotes_status"),
        _enum_check("pricing_mode", ARAZASI_MODOK, "ck_quotes_pricing_mode"),
        CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name="ck_quotes_discount_percent"),
        UniqueConstraint("number", "version", name="uq_quotes_number_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(10), nullable=False, default="HYPE")
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    event_date_from: Mapped[date | None] = mapped_column(Date)
    event_date_to: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", index=True)
    pricing_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="one_off")
    months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    discount_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    vat_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=27)
    summary_label: Mapped[str | None] = mapped_column(String(120))
    occasions_label: Mapped[str | None] = mapped_column(String(40))
    note_text: Mapped[str | None] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id", ondelete="SET NULL"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("quote_templates.id", ondelete="SET NULL"))
    #: A nettó végösszeg (a nem opcionális sorok − kedvezmény) - a lista és a
    #: keresés miatt tároljuk; minden tételmódosítás újraszámolja.
    net_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list[QuoteItem]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuoteItem.sort_order"
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        CheckConstraint(
            "line_discount_percent >= 0 AND line_discount_percent <= 100", name="ck_quote_items_line_discount"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("quote_catalog_items.id", ondelete="SET NULL"), index=True
    )
    section: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text)
    occasions: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    unit: Mapped[str | None] = mapped_column(String(20))
    #: Ár-snapshot: a hozzáadás pillanatában másolódik a katalógusból.
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    #: Opcionális sor: nem számít bele a végösszegbe (külön blokk az exportban).
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quote: Mapped[Quote] = relationship(back_populates="items")
