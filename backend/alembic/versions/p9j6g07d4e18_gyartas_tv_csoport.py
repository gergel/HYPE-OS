"""Gyártás-TV: az utómunka-állapot TV-oszlopa.

A gyártási szobában kirakott, élő Gyártás-TV oldal (lásd
services/gyartas_tv.py) az aktív vágásokat négy oszlopba sorolja: épp vágják,
ellenőrzésen, kiküldhető, gyártásra vár. Az állapotok szabad szövegek, ezért
alapból a nevük dönt; ezzel a mezővel az admin állapotonként felülírhatja
(„rejtett" = ne jelenjen meg). Üres = automatikus.

Revision ID: p9j6g07d4e18
Revises: o8i5f96c3d07
"""

import sqlalchemy as sa
from alembic import op

revision = "p9j6g07d4e18"
down_revision = "o8i5f96c3d07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliverable_status_configs", sa.Column("tv_csoport", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("deliverable_status_configs", "tv_csoport")
