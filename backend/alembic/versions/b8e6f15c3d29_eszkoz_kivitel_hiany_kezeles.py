"""Eszközkivitel: hiány-kezelés mezők (megoldás + kész jelölés).

A felhasználó kérése: ha a kód lejárta (a forgatás utolsó napja + 48 óra)
után is maradt hiány, a dashboard jól láthatóan kiírja, mi hiányzik és
melyik forgatásnál - ott magyarázat írható (mi lett a megoldás), és a
"kész" jelöléssel vehető le a figyelmeztetés. Lásd
models/eszkoz_kivitel.py és routes/eszkoz_kivitel.hianyok.

Revision ID: b8e6f15c3d29
Revises: a7d5e93c1f28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8e6f15c3d29"
down_revision = "a7d5e93c1f28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eszkoz_kivitelek", sa.Column("hiany_megoldas", sa.Text(), nullable=True))
    op.add_column(
        "eszkoz_kivitelek",
        sa.Column("hiany_megoldva", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("eszkoz_kivitelek", "hiany_megoldva")
    op.drop_column("eszkoz_kivitelek", "hiany_megoldas")
