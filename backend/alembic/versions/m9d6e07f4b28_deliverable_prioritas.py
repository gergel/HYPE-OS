"""Prioritás jelölő az utómunkán (a felhasználó kérése): a kiemelt anyag
kártyája piros körvonalat kap az Utómunka táblán, amíg kész/kiküldhető
állapotba nem kerül - a vágó innen tudja, mivel kezdjen.

Revision ID: m9d6e07f4b28
Revises: l8c5d96e3a17
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "m9d6e07f4b28"
down_revision = "l8c5d96e3a17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deliverables",
        sa.Column("prioritas", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("deliverables", "prioritas")
