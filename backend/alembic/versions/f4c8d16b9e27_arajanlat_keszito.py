"""Árajánlat-készítő: arajanlatok + arajanlat_tetelek táblák.

A felhasználó kérése: külön oldal árajánlat-készítéshez (saját
hozzáféréssel), alap tétel-katalógussal és visszahívható ajánlat-sablonokkal
- lásd models/arajanlat.py.

Revision ID: f4c8d16b9e27
Revises: e3b7c95a1d48
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f4c8d16b9e27"
down_revision = "e3b7c95a1d48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arajanlatok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(length=255), nullable=False),
        sa.Column("sablon", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("brand", sa.String(length=20), nullable=False, server_default="hype"),
        sa.Column("ugyfel", sa.String(length=255), nullable=True),
        sa.Column("vegosszeg", sa.Numeric(14, 2), nullable=True),
        sa.Column("adat", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "arajanlat_tetelek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(length=255), nullable=False),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("szekcio", sa.String(length=100), nullable=True),
        sa.Column("egysegar", sa.Numeric(12, 2), nullable=True),
        sa.Column("sorrend", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("arajanlat_tetelek")
    op.drop_table("arajanlatok")
