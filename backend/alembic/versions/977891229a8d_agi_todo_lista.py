"""ÁGI to-do lista tábla

Revision ID: 977891229a8d
Revises: 33ba68750e0f
Create Date: 2026-08-30 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "977891229a8d"
down_revision = "33ba68750e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agi_todo_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feladat", sa.String(length=500), nullable=False),
        sa.Column("allapot", sa.String(length=50), nullable=True),
        sa.Column("ugyfel", sa.String(length=255), nullable=True),
        sa.Column("hatarido", sa.Date(), nullable=True),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("kovetkezo_lepes", sa.Text(), nullable=True),
        sa.Column("csatolt_link", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("agi_todo_items")
