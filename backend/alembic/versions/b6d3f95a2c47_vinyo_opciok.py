"""A vinyók hivatalos névlistája a board-configban.

A Notion "Vinyók" multi-select opcióiból szinkronizálva (lásd
notion_import/importers_wave2.import_vinyo_sync) - eddig egy kódban rögzített
lista volt, ami a Notion-változásoktól elcsúszott.

Revision ID: b6d3f95a2c47
Revises: a9e4c72d5b18
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "b6d3f95a2c47"
down_revision = "a9e4c72d5b18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliverable_board_configs", sa.Column("vinyo_opciok", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("deliverable_board_configs", "vinyo_opciok")
