"""Bevétel projektkód nélkül is felvehető (a felhasználó kérése): a
revenues.project_code_id NULL-ozható lett. A kintlévőség-nézet
projektkódonként megy, ott a kód nélküli sor nem jelenik meg; az éves/havi
összesítőkbe beszámít.

Revision ID: q4i1h52e9g73
Revises: p3h0g41d8f62
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op

revision = "q4i1h52e9g73"
down_revision = "p3h0g41d8f62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("revenues", "project_code_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Csak akkor fut le, ha már nincs projektkód nélküli bevétel.
    op.alter_column("revenues", "project_code_id", existing_type=sa.Integer(), nullable=False)
