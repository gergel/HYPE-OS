"""Kiadások: ÁFA nélkül a bruttó a nettó értéke.

A felhasználó kérése: ahol a kiadáson nincs "+ÁFA" jelölve, ott a bruttó
ugyanaz az összeg, mint a nettó - a régi soroknál viszont ilyenkor a bruttó
sokszor üresen maradt. Ez a migráció az ÜRES bruttót tölti fel a nettóval a
nem-ÁFÁ-s sorokon; a kézzel beírt bruttóhoz nem nyúl, ezért akárhányszor
lefuttatható. Az új/módosított tételeknél ugyanezt a szerver számolja (lásd
routes/finance._afa_brutto).

Revision ID: b9e4f72a6c15
Revises: a7f3e85c9d24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b9e4f72a6c15"
down_revision = "a7f3e85c9d24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A "+ÁFA" igen-változatai ugyanazok, mint routes/finance._plusz_afa_jelolt.
    op.execute(
        sa.text(
            "UPDATE expenses SET brutto = netto "
            "WHERE brutto IS NULL AND netto IS NOT NULL "
            "AND lower(coalesce(trim(plusz_afa), '')) NOT IN ('igen', 'true', '+afa', '+áfa')"
        )
    )


def downgrade() -> None:
    # Nem visszafordítható - nem tudni, melyik bruttó jött ebből.
    pass
