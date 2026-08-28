"""kp forgalom devizas es van szamla

Revision ID: 49be2bd0fac9
Revises: c7e2b498f1a3
Create Date: 2026-08-28 12:00:00.000000

A KP forgalom soroknak eddig nem volt saját devizás felvezetése (lásd
services/penznem.py) és nem volt kézzel állítható "van számla" jelölésük sem
- a Számla oszlop eddig egy csak-attól-Van derived állapotot mutatott.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "49be2bd0fac9"
down_revision: Union[str, None] = "c7e2b498f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("kp_forgalmak", sa.Column("arfolyam", sa.Numeric(10, 4), nullable=True))
    op.add_column("kp_forgalmak", sa.Column("eredeti_penznem", sa.String(10), nullable=True))
    op.add_column("kp_forgalmak", sa.Column("eredeti_osszeg", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "kp_forgalmak",
        sa.Column("van_szamla", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("kp_forgalmak", "van_szamla", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("kp_forgalmak", "van_szamla")
    op.drop_column("kp_forgalmak", "eredeti_osszeg")
    op.drop_column("kp_forgalmak", "eredeti_penznem")
    op.drop_column("kp_forgalmak", "arfolyam")
