"""dokumentum csatolmanyok tabla

A szerződések, TIG-ek és számlák fájljait tároló, entitás-független
csatolmány-tábla. A fájl TARTALMA az R2-re kerül (lásd
services/document_storage.py), ide csak a hivatkozás - a Railway konténer
lemeze minden deploynál üres lappal indul, oda mentett dokumentum elveszne.

Revision ID: 3a4d1e536deb
Revises: 489fdbff9833
Create Date: 2026-08-04 11:55:35.210174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a4d1e536deb'
down_revision: Union[str, Sequence[str], None] = '489fdbff9833'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("kategoria", sa.String(length=30), nullable=False, server_default="egyeb"),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("meret_bajt", sa.Integer(), nullable=True),
        sa.Column("notion_forras", sa.String(length=700), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_attachments_entity", "document_attachments", ["entity_type", "entity_id"])
    op.create_index("ix_document_attachments_notion_forras", "document_attachments", ["notion_forras"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_document_attachments_notion_forras", table_name="document_attachments")
    op.drop_index("ix_document_attachments_entity", table_name="document_attachments")
    op.drop_table("document_attachments")
