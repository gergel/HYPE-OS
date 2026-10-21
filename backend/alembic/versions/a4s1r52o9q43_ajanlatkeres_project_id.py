"""Munkafelajánlás: a projekt a meglévő Projektek közül választva.

Az ajanlatkeresek.project_id a projects táblára mutat; a projekt_nev marad a
kiküldéskori pillanatkép (átnevezés/törlés nem hamisítja meg a leveleket).

Revision ID: a4s1r52o9q43
Revises: z3r0q41n8p42
"""

import sqlalchemy as sa
from alembic import op

revision = "a4s1r52o9q43"
down_revision = "z3r0q41n8p42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ajanlatkeresek", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ajanlatkeresek_project_id",
        "ajanlatkeresek",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ajanlatkeresek_project_id", "ajanlatkeresek", type_="foreignkey")
    op.drop_column("ajanlatkeresek", "project_id")
