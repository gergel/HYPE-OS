"""Eszközkivitel: lezárás-időpontok + nem leltári eszköz mezők.

A felhasználó kérése: a kezelő oldalon látszódjon, mikor zárták le a
kivitelt és a visszahozatalt, és legyen szabad mező a nem leltári (bérelt)
eszközöknek - lásd models/eszkoz_kivitel.py.

Revision ID: d9a3b75e8c64
Revises: c8f2a64d7b53
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d9a3b75e8c64"
down_revision = "c8f2a64d7b53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eszkoz_kivitelek", sa.Column("kivitel_lezarva_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("eszkoz_kivitelek", sa.Column("vissza_lezarva_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("eszkoz_kivitelek", sa.Column("kulso_kivitel", sa.Text(), nullable=True))
    op.add_column("eszkoz_kivitelek", sa.Column("kulso_vissza", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("eszkoz_kivitelek", "kulso_vissza")
    op.drop_column("eszkoz_kivitelek", "kulso_kivitel")
    op.drop_column("eszkoz_kivitelek", "vissza_lezarva_at")
    op.drop_column("eszkoz_kivitelek", "kivitel_lezarva_at")
