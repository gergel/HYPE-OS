"""Megrendelői szerződés és TIG: átírható kísérőlevél.

A felhasználó kérése: a projektkód oldalán egy kapcsolóval lehessen
szerkeszteni a kimenő levelet (tárgy, szöveg) - ha nem írják át, az alap
levél megy. A papíron tároljuk, hogy a mentés után se vesszen el. Két-két
új, üres (nullable) oszlop - meglévő adat nem változik. Visszafordítható.

Revision ID: j0m1r2e3m4a5
Revises: i9g0e1n2e3r4
"""

import sqlalchemy as sa
from alembic import op

revision = "j0m1r2e3m4a5"
down_revision = "i9g0e1n2e3r4"
branch_labels = None
depends_on = None

_TABLAK = ("megrendeloi_szerzodesek", "megrendeloi_tigek")


def upgrade() -> None:
    for tabla in _TABLAK:
        op.add_column(tabla, sa.Column("email_targy", sa.String(length=500), nullable=True))
        op.add_column(tabla, sa.Column("email_szoveg", sa.Text(), nullable=True))


def downgrade() -> None:
    for tabla in _TABLAK:
        op.drop_column(tabla, "email_szoveg")
        op.drop_column(tabla, "email_targy")
