"""Profil (saját szín + profilkép) és vinyó-színek.

- employees.szin: a munkatárs saját színe (#rrggbb) - a neve ezen jelenik meg
  pl. az utómunka kártyákon (a profil oldalán állítja).
- employees.profilkep: profilkép data-URL-ként, a böngészőben kicsinyítve.
- deliverable_board_configs.vinyo_szinek: {vinyó név -> "#rrggbb"} a vinyó-
  nézet oszlopainak/kártyasorainak színezéséhez.

Revision ID: y2q9p30m7o41
Revises: x1p8o29l6n40
"""

import sqlalchemy as sa
from alembic import op

revision = "y2q9p30m7o41"
down_revision = "x1p8o29l6n40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("szin", sa.String(length=9), nullable=True))
    op.add_column("employees", sa.Column("profilkep", sa.Text(), nullable=True))
    op.add_column("deliverable_board_configs", sa.Column("vinyo_szinek", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("deliverable_board_configs", "vinyo_szinek")
    op.drop_column("employees", "profilkep")
    op.drop_column("employees", "szin")
