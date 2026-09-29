"""Kiadás: `kp_fedezet` jelölő (házipénztár-fedezet).

Egy új, alapból hamis oszlop az `expenses` táblán - a meglévő sorok nem
változnak (mind „nem fedezet” marad). Visszafordítható.

Revision ID: v5q2n63k0l84
Revises: u4p1m52j9k73
"""

import sqlalchemy as sa
from alembic import op

revision = "v5q2n63k0l84"
down_revision = "u4p1m52j9k73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("kp_fedezet", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("expenses", "kp_fedezet")
