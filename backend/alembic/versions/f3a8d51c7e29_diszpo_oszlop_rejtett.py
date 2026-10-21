"""HYPE 2026 tábla: oszlop elrejthető.

A már nem kellő oszlopok (pl. kilépett munkatárs) a felületről eltüntethetők
az adatuk elvesztése nélkül - lásd models/diszpo_tabla.DiszpoOszlop.rejtett.

Revision ID: f3a8d51c7e29
Revises: e7c2a94d1b38
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "f3a8d51c7e29"
down_revision = "e7c2a94d1b38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "diszpo_oszlopok",
        sa.Column("rejtett", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("diszpo_oszlopok", "rejtett")
