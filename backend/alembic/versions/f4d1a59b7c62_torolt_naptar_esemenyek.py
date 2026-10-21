"""Törölt naptár-események táblája.

A felhasználó kérése: a rendszerből kitörölt, de a Google Naptárban még élő
projektet a szinkron ne hozza vissza - lásd models/torolt_naptar_esemeny.py.

Revision ID: f4d1a59b7c62
Revises: e3b9c48f6a51
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f4d1a59b7c62"
down_revision = "e3b9c48f6a51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "torolt_naptar_esemenyek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("projekt_nev", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_torolt_naptar_esemenyek_event_id", "torolt_naptar_esemenyek", ["event_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_torolt_naptar_esemenyek_event_id", table_name="torolt_naptar_esemenyek")
    op.drop_table("torolt_naptar_esemenyek")
