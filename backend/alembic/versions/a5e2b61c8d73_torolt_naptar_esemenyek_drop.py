"""A törölt naptár-események táblájának eltávolítása.

A felhasználó meggondolta (az előző kör után): a rendszerből törölt, de a
naptárban még élő eseményt a szinkron IGENIS hozza vissza - a tiltólista
tehát nem kell. A visszahozást a törléskor nullázott szinkron-jelző oldja
meg (lásd routes/projects._projekt_torles_elott): a következő kör teljes
szinkront futtat, ami a még élő eseményből újra létrehozza a projektet.

Revision ID: a5e2b61c8d73
Revises: f4d1a59b7c62
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a5e2b61c8d73"
down_revision = "f4d1a59b7c62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_torolt_naptar_esemenyek_event_id", table_name="torolt_naptar_esemenyek")
    op.drop_table("torolt_naptar_esemenyek")


def downgrade() -> None:
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
