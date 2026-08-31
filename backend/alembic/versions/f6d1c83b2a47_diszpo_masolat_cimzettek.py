"""Diszpó másolat-címzettek: kik kapják CC-ben az összes kimenő diszpót.

A Beállítások oldalon, adminként állítható névsor - a leveleken a HYPE_CC
env fix címei MELLÉ kerülnek (lásd services/dispo.py és google_email.py).

Revision ID: f6d1c83b2a47
Revises: e2b7c94f1a58
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "f6d1c83b2a47"
down_revision = "e2b7c94f1a58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diszpo_masolat_cimzettek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("diszpo_masolat_cimzettek")
