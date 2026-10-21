"""Bevétel fizetési módja (készpénz / átutalás) - ebből számol a kassza

A kiadásnál ez már megvolt (`kifizetes_modja`), a bevételnél nem - így a
kasszába csak a kimenő oldal látszott (lásd services/fizetesi_mod.py).

Revision ID: d7e2b41f8c96
Revises: c4a91e7b25d0
"""

import sqlalchemy as sa
from alembic import op

revision = "d7e2b41f8c96"
down_revision = "c4a91e7b25d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "revenues",
        sa.Column(
            "fizetes_modja",
            sa.String(length=50),
            nullable=True,
            comment="Készpénz / Átutalás - ebből számol a kassza",
        ),
    )


def downgrade() -> None:
    op.drop_column("revenues", "fizetes_modja")
