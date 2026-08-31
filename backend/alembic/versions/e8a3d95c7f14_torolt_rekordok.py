"""torolt_rekordok: a törlés-visszavonás (Ctrl+Z) pillanatképei.

A generikus törlés ide menti a rekord oszlopait törlés előtt, a
POST /visszavonas/torles/{id} pedig ebből állítja vissza a sort az eredeti
azonosítójával (lásd services/visszavonas.py).

Revision ID: e8a3d95c7f14
Revises: d2e8b47f9a31
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "e8a3d95c7f14"
down_revision = "d2e8b47f9a31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "torolt_rekordok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tabla", sa.String(length=100), nullable=False, index=True),
        sa.Column("rekord_id", sa.Integer(), nullable=False),
        sa.Column("adatok", sa.JSON(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True, index=True),
        sa.Column("visszaallitva", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("torolt_rekordok")
