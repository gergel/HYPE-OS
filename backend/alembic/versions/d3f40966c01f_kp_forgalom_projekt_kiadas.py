"""kp forgalom projekt kiadas

Revision ID: d3f40966c01f
Revises: 49be2bd0fac9
Create Date: 2026-08-28 13:00:00.000000

A "Projekt kiadás" mező: melyik projekthez tartozik ez a KP forgalom sor -
önálló hivatkozás, FÜGGETLEN az expense_id-tól (lásd models/finance.py
KpForgalom.project_code_id megjegyzése).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f40966c01f"
down_revision: Union[str, None] = "49be2bd0fac9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("kp_forgalmak", sa.Column("project_code_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "kp_forgalmak_project_code_id_fkey",
        "kp_forgalmak",
        "project_codes",
        ["project_code_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("kp_forgalmak_project_code_id_fkey", "kp_forgalmak", type_="foreignkey")
    op.drop_column("kp_forgalmak", "project_code_id")
