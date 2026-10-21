"""Vágói játék: a nyeremény kihirdetésének időpontja.

A kihirdetéstől 5 napig minden aktív vágó dashboardján megjelenik az e havi
nyeremény (lásd routes/dashboard.summary). A meglévő, már kihirdetett
hónapokat nem töltjük vissza: azok nyereményét a csapat már ismeri, nem kell
utólag feldobni senkinek.

Revision ID: c9d2e74a5f18
Revises: b8c4f61d2e93
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d2e74a5f18"
down_revision = "b8c4f61d2e93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vago_jatek_honapok",
        sa.Column("nyeremeny_kihirdetve_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vago_jatek_honapok", "nyeremeny_kihirdetve_at")
