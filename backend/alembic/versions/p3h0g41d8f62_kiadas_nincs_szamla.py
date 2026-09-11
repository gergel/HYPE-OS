"""NINCS SZÁMLA jelölő a kiadásokon (a felhasználó kérése): a felviteli
űrlap kapcsolójával jelölhető, hogy a tételhez nem is lesz számla/blokk -
a felületek ne hiányzó számlaként mutassák.

Revision ID: p3h0g41d8f62
Revises: o2g9f30c7e51
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op

revision = "p3h0g41d8f62"
down_revision = "o2g9f30c7e51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("nincs_szamla", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("expenses", "nincs_szamla")
