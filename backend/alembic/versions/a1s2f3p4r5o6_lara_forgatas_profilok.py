"""Lara forgatás-ismerete: `aa_forgatas_profilok` (modell / ember által pontosított profil).

Csak új tábla (Lara saját táblája), a forgatásokhoz nem nyúl; adat-átírás
nincs. Visszafordítható.

Revision ID: a1s2f3p4r5o6
Revises: y8t5q96o3p17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a1s2f3p4r5o6"
down_revision = "y8t5q96o3p17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aa_forgatas_profilok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profil", JSONB(), nullable=False),
        sa.Column("forras", sa.String(20), nullable=False),
        sa.Column("modell", sa.String(120), nullable=True),
        sa.Column("forras_ujjlenyomat", sa.String(64), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_aa_forgatas_profilok_project_id", "aa_forgatas_profilok", ["project_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_aa_forgatas_profilok_project_id", table_name="aa_forgatas_profilok")
    op.drop_table("aa_forgatas_profilok")
