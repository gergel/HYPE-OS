"""Adminisztráció ellenőrzése: a heti áttekintés ideje és a figyelés kezdete.

A felhasználó kérése: Lara HETENTE nézze át a kijelölt munkatárs munkáját,
és az egész ellenőrzés csak attól a naptól nézzen, amióta a kolléga itt
dolgozik (2026.10.05.). Két új, üres (nullable) oszlop - meglévő adat nem
változik. Visszafordítható.

Revision ID: g7h8e9t0i1a2
Revises: f6a7d8m9e0l1
"""

import sqlalchemy as sa
from alembic import op

revision = "g7h8e9t0i1a2"
down_revision = "f6a7d8m9e0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_ellenorzes_beallitasok", sa.Column("heti_attekintes_at", sa.DateTime(timezone=True)))
    op.add_column("admin_ellenorzes_beallitasok", sa.Column("figyeles_kezdete", sa.Date()))


def downgrade() -> None:
    op.drop_column("admin_ellenorzes_beallitasok", "figyeles_kezdete")
    op.drop_column("admin_ellenorzes_beallitasok", "heti_attekintes_at")
