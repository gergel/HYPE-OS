"""Megbeszélt díj: mennyiért vállalja az adott ember az adott napot

A diszpó írásakor, a stábtag felvételekor derül ki, mennyiért vállalja a
forgatást - a szerződést és a TIG-et viszont hetekkel később, más ember
adminisztrálja, akinek pont ez az összeg kell a papírra. Eddig ez sehol nem
volt rögzítve, ezért vagy visszakereste valaki egy üzenetváltásból, vagy
tippelt (lásd models/project_szamlazo.py).

Revision ID: e2b7c4915d63
Revises: d1a4e6b3c827
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b7c4915d63"
down_revision: Union[str, Sequence[str], None] = "d1a4e6b3c827"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_szamlazok",
        sa.Column(
            "megbeszelt_dij",
            sa.Numeric(12, 2),
            nullable=True,
            comment="Ennyiért vállalja ezt a napot - nettó",
        ),
    )
    op.add_column("project_szamlazok", sa.Column("dij_megjegyzes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_szamlazok", "dij_megjegyzes")
    op.drop_column("project_szamlazok", "megbeszelt_dij")
