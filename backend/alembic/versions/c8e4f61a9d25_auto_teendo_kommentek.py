"""Hozzászólások az autó-teendőkhöz.

Chat-szerű beszélgetés minden autó-teendő alatt (lásd routes/autok.py
komment-végpontjai) - ugyanaz a minta, mint a HYPE TO-DO és a FLÓRA
kommentjeinél.

Revision ID: c8e4f61a9d25
Revises: b3f9d24c6e81
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "c8e4f61a9d25"
down_revision = "b3f9d24c6e81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_teendo_kommentek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auto_teendo_id", sa.Integer(), sa.ForeignKey("auto_teendok.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auto_teendo_kommentek")
