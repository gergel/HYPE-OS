"""szamla csatolmany sajat bevetel sora

Revision ID: a1f9c3d7e264
Revises: d00bb3816b92
Create Date: 2026-08-25 16:00:00.000000

Egy feltöltött SZÁMLA fájl kifizetettnek jelölése mostantól SAJÁT bevétel-sort
nyit a Pénzügyekben (nem a projektkód egy közös sorát egészíti ki) - osztott
számlázásnál (több számla egy projektkódon) így mindegyiknek külön összege és
külön kifizetési dátuma lehet. Ehhez kell a számla saját nettó/ÁFA összege, a
bevételekből való kihagyás lehetősége, és a nyitott Revenue-ra mutató kapocs
(a visszavonáshoz). Lásd services/megrendeloi_szamla.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f9c3d7e264"
down_revision: Union[str, None] = "d00bb3816b92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("document_attachments", sa.Column("netto", sa.Numeric(12, 2), nullable=True))
    op.add_column("document_attachments", sa.Column("plusz_afa", sa.Boolean(), nullable=True))
    op.add_column(
        "document_attachments",
        sa.Column("bevetelbe_ne_keruljon", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("document_attachments", "bevetelbe_ne_keruljon", server_default=None)
    op.add_column("document_attachments", sa.Column("bevetel_kihagyas_oka", sa.Text(), nullable=True))
    op.add_column("document_attachments", sa.Column("revenue_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_document_attachments_revenue_id",
        "document_attachments",
        "revenues",
        ["revenue_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_document_attachments_revenue_id", "document_attachments", type_="foreignkey")
    op.drop_column("document_attachments", "revenue_id")
    op.drop_column("document_attachments", "bevetel_kihagyas_oka")
    op.drop_column("document_attachments", "bevetelbe_ne_keruljon")
    op.drop_column("document_attachments", "plusz_afa")
    op.drop_column("document_attachments", "netto")
