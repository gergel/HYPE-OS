"""Belsős TIG: `honap_rogzitve` - kézzel rögzített hónap.

A visszamenőleges rendezés áthelyezése állítja be: ilyenkor a TIG hónapját
nem a dátumaiból számoljuk. Csak egy új oszlop false alapértékkel - meglévő
adat nem változik. Visszafordítható.

Revision ID: d4b5t6i7g8r9
Revises: c3s4z5e6m7l8
"""

import sqlalchemy as sa
from alembic import op

revision = "d4b5t6i7g8r9"
down_revision = "c3s4z5e6m7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "internal_performance_certificates",
        sa.Column("honap_rogzitve", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("internal_performance_certificates", "honap_rogzitve")
