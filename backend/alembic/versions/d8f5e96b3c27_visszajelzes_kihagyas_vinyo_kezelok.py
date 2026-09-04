"""Visszajelzés kihagyása + vinyó-kezelő jogosultság.

- feedbacks.kihagyva: az automatikusan feldobott visszajelzés-űrlap
  kihagyható, de csak indoklással - az ilyen sor jelölése (a felhasználó
  kérése).
- deliverable_board_configs.vinyo_kezelo_employee_ids: kik kezelhetik a
  vinyó-neveket az adminon kívül (külön, adminból adható jogosultság).

Revision ID: d8f5e96b3c27
Revises: c7e4d83f1a95
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "d8f5e96b3c27"
down_revision = "c7e4d83f1a95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feedbacks",
        sa.Column("kihagyva", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "deliverable_board_configs",
        sa.Column("vinyo_kezelo_employee_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deliverable_board_configs", "vinyo_kezelo_employee_ids")
    op.drop_column("feedbacks", "kihagyva")
