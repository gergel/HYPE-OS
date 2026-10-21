"""Külsős TIG: generálás kiküldés nélkül.

A felhasználó kérése: az utókövetésben lehessen csak legenerálni a TIG-et -
felkerül a rendszerbe, de nem megy ki e-mailben (a generálás és küldés
megmarad mellette). A `csak_generalva` jelzi, hogy a kész (Kiküldve
állapotú) TIG nem ment ki levélben. Új oszlop, alapból hamis - meglévő adat
nem változik. Visszafordítható.

Revision ID: i9g0e1n2e3r4
Revises: h8e9m0a1i2l3
"""

import sqlalchemy as sa
from alembic import op

revision = "i9g0e1n2e3r4"
down_revision = "h8e9m0a1i2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "performance_certificates",
        sa.Column("csak_generalva", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("performance_certificates", "csak_generalva")
