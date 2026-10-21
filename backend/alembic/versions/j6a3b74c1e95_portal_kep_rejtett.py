"""Portál kép: rejtett jelölés.

A felhasználó kérése: ha egy mappa rejtett, a feltöltő linken oda érkező
képek (és videók) automatikusan rejtettek legyenek, és ezt a feltöltő ne
tudja megváltoztatni. A videónak már van rejtett mezője - most a kép is kap.

Revision ID: j6a3b74c1e95
Revises: i5f2a63b9d84
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op

revision = "j6a3b74c1e95"
down_revision = "i5f2a63b9d84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_images",
        sa.Column("rejtett", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("portal_images", "rejtett")
