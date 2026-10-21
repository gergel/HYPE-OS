"""HYPE TO-DO LIST és FLÓRA táblák

Revision ID: 33ba68750e0f
Revises: 73200ef6946b
Create Date: 2026-08-30 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "33ba68750e0f"
down_revision = "73200ef6946b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hype_todo_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feladat", sa.String(length=500), nullable=False),
        sa.Column("allapot", sa.String(length=50), nullable=True),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("kategoria", sa.String(length=100), nullable=True),
        sa.Column("hatarido", sa.Date(), nullable=True),
        sa.Column("csatolando_link", sa.String(length=1000), nullable=True),
        sa.Column("letrehozas_idopontja", sa.DateTime(), nullable=True),
        sa.Column("aki_felvezette_id", sa.Integer(), nullable=True),
        sa.Column("ellenorzes_felelos_id", sa.Integer(), nullable=True),
        sa.Column("aki_ellenorizte_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["aki_felvezette_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["ellenorzes_felelos_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["aki_ellenorizte_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hype_todo_felelosok",
        sa.Column("hype_todo_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["hype_todo_id"], ["hype_todo_items.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("hype_todo_id", "employee_id"),
    )
    op.create_table(
        "flora_feladatok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("megnevezes", sa.String(length=500), nullable=False),
        sa.Column("allapot", sa.String(length=50), nullable=True),
        sa.Column("cimke", sa.String(length=255), nullable=True),
        sa.Column("hatarido", sa.DateTime(), nullable=True),
        sa.Column("kesz_anyag_linkje", sa.String(length=1000), nullable=True),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("letrehozas_idopontja", sa.DateTime(), nullable=True),
        sa.Column("felelos_id", sa.Integer(), nullable=True),
        sa.Column("felvezette_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["felelos_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["felvezette_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("flora_feladatok")
    op.drop_table("hype_todo_felelosok")
    op.drop_table("hype_todo_items")
