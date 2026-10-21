"""Kiadás: külön "mire ment" leírás + ÁFA-százalék.

A `megnevezes` a felületen mostantól "Cégnév" (kinek fizettünk), a
`kiadas_leiras` az új "Megnevezés" (mire ment); az `afa_szazalek`-ból a
szerver számolja a bruttót, ha a nettóhoz "+ÁFA"-t jelöltek (lásd
routes/finance.py).

Revision ID: e7c2a94d1b38
Revises: d4b7e29c8f16
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "e7c2a94d1b38"
down_revision = "d4b7e29c8f16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("kiadas_leiras", sa.Text(), nullable=True))
    op.add_column("expenses", sa.Column("afa_szazalek", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "afa_szazalek")
    op.drop_column("expenses", "kiadas_leiras")
