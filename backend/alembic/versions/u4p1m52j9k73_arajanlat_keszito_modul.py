"""Árajánlat-készítő modul: `quote_*` táblák és `quotes`.

Csak új táblák; a korábbi szerkesztő táblái (`arajanlatok`,
`arajanlat_tetelek`) érintetlenek, adat-átírás nincs. A katalógus / sablon
seed NEM itt fut (lásd app/quotes/seed.py). Visszafordítható.

Revision ID: u4p1m52j9k73
Revises: t3o0l41i8j62
"""

import sqlalchemy as sa
from alembic import op

revision = "u4p1m52j9k73"
down_revision = "t3o0l41i8j62"
branch_labels = None
depends_on = None

_EGYSEGEK = "('fo_nap','db_nap','nap','ora','alkalom','db','project','km','fo','honap')"
_BRANDEK = "('HYPE','CB')"
_MODOK = "('one_off','monthly')"


def _idobelyeg():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "quote_catalog_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "quote_catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("quote_catalog_categories.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="db"),
        sa.Column("base_price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("price_min", sa.BigInteger(), nullable=True),
        sa.Column("price_max", sa.BigInteger(), nullable=True),
        sa.Column("price_median", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("seed_key", sa.String(20), nullable=True, unique=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint(f"unit IN {_EGYSEGEK}", name="ck_quote_catalog_items_unit"),
    )
    op.create_index("ix_quote_catalog_items_category_id", "quote_catalog_items", ["category_id"])
    op.create_table(
        "quote_catalog_price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_item_id", sa.Integer(),
                  sa.ForeignKey("quote_catalog_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_price", sa.BigInteger(), nullable=True),
        sa.Column("new_price", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_quote_catalog_price_history_catalog_item_id", "quote_catalog_price_history",
                    ["catalog_item_id"])
    op.create_table(
        "quote_note_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_idobelyeg(),
    )
    op.create_table(
        "quote_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(10), nullable=False, server_default="HYPE"),
        sa.Column("pricing_mode", sa.String(10), nullable=False, server_default="one_off"),
        sa.Column("summary_label", sa.String(120), nullable=True),
        sa.Column("occasions_label", sa.String(40), nullable=True),
        sa.Column("typical_total", sa.BigInteger(), nullable=True),
        sa.Column("default_note_id", sa.Integer(),
                  sa.ForeignKey("quote_note_presets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("seed_key", sa.String(20), nullable=True, unique=True),
        *_idobelyeg(),
        sa.CheckConstraint(f"brand IN {_BRANDEK}", name="ck_quote_templates_brand"),
        sa.CheckConstraint(f"pricing_mode IN {_MODOK}", name="ck_quote_templates_pricing_mode"),
    )
    op.create_table(
        "quote_template_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(),
                  sa.ForeignKey("quote_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_item_id", sa.Integer(),
                  sa.ForeignKey("quote_catalog_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("section", sa.String(120), nullable=True),
        sa.Column("name_override", sa.String(255), nullable=True),
        sa.Column("description_override", sa.Text(), nullable=True),
        sa.Column("unit_override", sa.String(20), nullable=True),
        sa.Column("default_occasions", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("default_quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("price_override", sa.BigInteger(), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_quote_template_items_template_id", "quote_template_items", ["template_id"])
    op.create_table(
        "quote_number_counters",
        sa.Column("brand", sa.String(10), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("brand", sa.String(10), nullable=False, server_default="HYPE"),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("event_date_from", sa.Date(), nullable=True),
        sa.Column("event_date_to", sa.Date(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("pricing_mode", sa.String(10), nullable=False, server_default="one_off"),
        sa.Column("months", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vat_percent", sa.Numeric(5, 2), nullable=False, server_default="27"),
        sa.Column("summary_label", sa.String(120), nullable=True),
        sa.Column("occasions_label", sa.String(40), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_quote_id", sa.Integer(), sa.ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_id", sa.Integer(),
                  sa.ForeignKey("quote_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("net_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        *_idobelyeg(),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"brand IN {_BRANDEK}", name="ck_quotes_brand"),
        sa.CheckConstraint("status IN ('draft','sent','accepted','rejected','archived')", name="ck_quotes_status"),
        sa.CheckConstraint(f"pricing_mode IN {_MODOK}", name="ck_quotes_pricing_mode"),
        sa.CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name="ck_quotes_discount_percent"),
        sa.UniqueConstraint("number", "version", name="uq_quotes_number_version"),
    )
    op.create_index("ix_quotes_number", "quotes", ["number"])
    op.create_index("ix_quotes_client_id", "quotes", ["client_id"])
    op.create_index("ix_quotes_status", "quotes", ["status"])
    op.create_table(
        "quote_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_item_id", sa.Integer(),
                  sa.ForeignKey("quote_catalog_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("section", sa.String(120), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occasions", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("unit_price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("line_discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("line_discount_percent >= 0 AND line_discount_percent <= 100",
                           name="ck_quote_items_line_discount"),
    )
    op.create_index("ix_quote_items_quote_id", "quote_items", ["quote_id"])
    op.create_index("ix_quote_items_catalog_item_id", "quote_items", ["catalog_item_id"])


def downgrade() -> None:
    op.drop_table("quote_items")
    op.drop_table("quotes")
    op.drop_table("quote_number_counters")
    op.drop_table("quote_template_items")
    op.drop_table("quote_templates")
    op.drop_table("quote_note_presets")
    op.drop_table("quote_catalog_price_history")
    op.drop_table("quote_catalog_items")
    op.drop_table("quote_catalog_categories")
