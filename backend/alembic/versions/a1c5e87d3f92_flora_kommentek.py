"""FLÓRA hozzászólások: chat a feladatok oldalán + a Notion-kommentek átvétele.

Ugyanaz a minta, mint az Utómunka és a Project Code hozzászólásainál - a
Notion-import a kártyák Notion-beli kommentjeit is ide hozza át (lásd
notion_import/importers_wave4.import_flora_design).

Revision ID: a1c5e87d3f92
Revises: f6d1c83b2a47
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c5e87d3f92"
down_revision = "f6d1c83b2a47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flora_kommentek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flora_feladat_id", sa.Integer(), sa.ForeignKey("flora_feladatok.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("flora_kommentek")
