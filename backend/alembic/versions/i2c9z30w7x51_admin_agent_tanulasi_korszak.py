"""HYRON: tanulási korszak a példákon.

A cég 2026. szeptember 1. óta a HYPE OS felületén dolgozik (előtte Notionben).
A megfigyelt példák mellé eltesszük a forrásrekord keletkezését és azt, hogy
a „régi korszakból" (a tanulás kezdete előtti vagy Notionből importált rekord)
származik-e — a régi példák nem lesznek új jelöltek, a már jóváhagyottak pedig
csak az újak után, kisebb súllyal kerülnek elő. Additív.

Revision ID: i2c9z30w7x51
Revises: h1b8y29v6w50
"""

import sqlalchemy as sa
from alembic import op

revision = "i2c9z30w7x51"
down_revision = "h1b8y29v6w50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("aa_memory_chunks", sa.Column("forras_keletkezes", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "aa_memory_chunks",
        sa.Column("regi_korszak", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("aa_memory_chunks", "regi_korszak")
    op.drop_column("aa_memory_chunks", "forras_keletkezes")
