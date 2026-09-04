"""Portál mappa: rejtett jelölés (egész mappa elrejtése az ügyfél elől).

A felhasználó kérése: ne csak videót, egész mappát is el lehessen rejteni -
az ügyfél a portálon nem látja, a belsős (portál-jogú, bejelentkezett) néző
viszont feltűnő jelöléssel igen.

Revision ID: g3d9e41f7b62
Revises: f2c8d39e6a51
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "g3d9e41f7b62"
down_revision = "f2c8d39e6a51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_folders",
        sa.Column("rejtett", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("portal_folders", "rejtett")
