"""Portál videó: "csak belső ellenőrzésre" (rejtett) jelölés.

A felhasználó kérése: a vágó gyakran csak ellenőrzésre tölt fel egy videót,
amit az ügyfél még nem láthat - pedig a portál linkje már kint van nála
(ott kapta a képeket/korábbi anyagokat). A rejtett videó a publikus portálon
és a mappa-megosztásban nem jelenik meg, csak az adminon (és a videó saját,
szándékosan kiadott megosztó linkjén).

Revision ID: f2c8d39e6a51
Revises: e1b7c28d5f49
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "f2c8d39e6a51"
down_revision = "e1b7c28d5f49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_videos",
        sa.Column("rejtett", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("portal_videos", "rejtett")
