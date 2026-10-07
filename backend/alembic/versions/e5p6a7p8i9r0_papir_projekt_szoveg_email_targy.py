"""Alvállalkozói szerződés és külsős TIG: egyedi projekt-szöveg és e-mail tárgy.

Ha egy papír sok projektre szól, a felhasználó megadhatja, mi álljon a
dokumentumon a projektek felsorolása helyett (`projekt_szoveg`), és mi legyen
a kimenő levél tárgya (`email_targy`). Két-két új, üres (nullable) oszlop -
meglévő adat nem változik. Visszafordítható.

Revision ID: e5p6a7p8i9r0
Revises: d4b5t6i7g8r9
"""

import sqlalchemy as sa
from alembic import op

revision = "e5p6a7p8i9r0"
down_revision = "d4b5t6i7g8r9"
branch_labels = None
depends_on = None

_TABLAK = ("contracts", "performance_certificates")


def upgrade() -> None:
    for tabla in _TABLAK:
        op.add_column(tabla, sa.Column("projekt_szoveg", sa.Text(), nullable=True))
        op.add_column(tabla, sa.Column("email_targy", sa.String(length=500), nullable=True))


def downgrade() -> None:
    for tabla in _TABLAK:
        op.drop_column(tabla, "email_targy")
        op.drop_column(tabla, "projekt_szoveg")
