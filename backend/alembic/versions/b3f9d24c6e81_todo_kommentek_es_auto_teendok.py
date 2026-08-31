"""HYPE TO-DO hozzászólások + autónkénti teendők.

- hype_todo_kommentek: chat a feladatok oldalán, a Notion-kommentek
  átvételével (lásd notion_import/importers_wave4.import_hype_todo).
- auto_teendok: pipálható teendő-lista az Autók oldalán, járművenként
  (lásd routes/autok.py).

Revision ID: b3f9d24c6e81
Revises: a1c5e87d3f92
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "b3f9d24c6e81"
down_revision = "a1c5e87d3f92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hype_todo_kommentek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hype_todo_id", sa.Integer(), sa.ForeignKey("hype_todo_items.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "auto_teendok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auto_id", sa.Integer(), sa.ForeignKey("autok.id"), nullable=False, index=True),
        sa.Column("szoveg", sa.Text(), nullable=False),
        sa.Column("kesz", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("hatarido", sa.Date(), nullable=True),
        sa.Column("felelos_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auto_teendok")
    op.drop_table("hype_todo_kommentek")
