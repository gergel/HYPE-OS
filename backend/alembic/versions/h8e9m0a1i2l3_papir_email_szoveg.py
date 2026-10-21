"""Alvállalkozói szerződés és külsős TIG: átírható kísérőlevél-szöveg.

A felhasználó kérése: a kiküldés előtti előnézetben az alap e-mail szövegét
át lehessen írni, ha nem tetszik. A piszkozaton tároljuk (`email_szoveg`),
hogy a mentés után se vesszen el. Egy-egy új, üres (nullable) oszlop -
meglévő adat nem változik; üresen az alap szöveg megy, mint eddig.
Visszafordítható.

Revision ID: h8e9m0a1i2l3
Revises: g7h8e9t0i1a2
"""

import sqlalchemy as sa
from alembic import op

revision = "h8e9m0a1i2l3"
down_revision = "g7h8e9t0i1a2"
branch_labels = None
depends_on = None

_TABLAK = ("contracts", "performance_certificates")


def upgrade() -> None:
    for tabla in _TABLAK:
        op.add_column(tabla, sa.Column("email_szoveg", sa.Text(), nullable=True))


def downgrade() -> None:
    for tabla in _TABLAK:
        op.drop_column(tabla, "email_szoveg")
