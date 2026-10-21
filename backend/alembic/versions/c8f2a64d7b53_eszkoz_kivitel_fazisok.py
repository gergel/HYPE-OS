"""Eszközkivitel fázisok: allapot + megjegyzes oszlop.

A felhasználó kérése: előbb csak a kivitel, annak lezárása után a
visszahozatal (a kivitt lista nélkül, hogy ne lehessen belőle "csalni"),
végül a visszahozatal lezárásakor megadható észrevétel - lásd
models/eszkoz_kivitel.py.

Revision ID: c8f2a64d7b53
Revises: b7e1f93c5a42
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8f2a64d7b53"
down_revision = "b7e1f93c5a42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eszkoz_kivitelek",
        sa.Column("allapot", sa.String(length=20), nullable=False, server_default="kivitel"),
    )
    op.add_column("eszkoz_kivitelek", sa.Column("megjegyzes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("eszkoz_kivitelek", "megjegyzes")
    op.drop_column("eszkoz_kivitelek", "allapot")
