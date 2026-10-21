"""Felszerelés archiválása: `equipment.archivalva_at`, `archivalta_id`, `archivalas_oka`.

Csak új, üres oszlopok - meglévő adat nem változik (a régi, Notionből
örökölt `archive_statusz` szöveg érintetlen). Visszafordítható.

Revision ID: b2e3q4u5i6p7
Revises: a1s2f3p4r5o6
"""

import sqlalchemy as sa
from alembic import op

revision = "b2e3q4u5i6p7"
down_revision = "a1s2f3p4r5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("equipment", sa.Column("archivalva_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "equipment",
        sa.Column("archivalta_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("equipment", sa.Column("archivalas_oka", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment", "archivalas_oka")
    op.drop_column("equipment", "archivalta_id")
    op.drop_column("equipment", "archivalva_at")
