"""HYPE 2026 diszpó-tábla: a sorok is elrejthetők, ne csak az oszlopok.

A felhasználó kérése: a rég lezárt napok sorai eltüntethetők legyenek az
adatuk elvesztése nélkül - ugyanaz az elv, mint az oszlop-elrejtésnél
(models/diszpo_tabla.DiszpoSor.rejtett).

Revision ID: d8e5b47c2f96
Revises: c4f8a63e9b17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d8e5b47c2f96"
down_revision = "c4f8a63e9b17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "diszpo_sorok",
        sa.Column("rejtett", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("diszpo_sorok", "rejtett")
