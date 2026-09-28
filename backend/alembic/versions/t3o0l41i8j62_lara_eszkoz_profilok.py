"""Lara eszköz-ismerete: `aa_eszkoz_profilok` (modell / ember által pontosított profil).

Csak új tábla (Lara saját táblája), az eszköztörzshöz nem nyúl; adat-átírás
nincs. Visszafordítható.

Revision ID: t3o0l41i8j62
Revises: s2n9k30h7i51
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "t3o0l41i8j62"
down_revision = "s2n9k30h7i51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aa_eszkoz_profilok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profil", JSONB(), nullable=False),
        sa.Column("forras", sa.String(20), nullable=False),
        sa.Column("modell", sa.String(120), nullable=True),
        sa.Column("forras_ujjlenyomat", sa.String(64), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_aa_eszkoz_profilok_equipment_id", "aa_eszkoz_profilok", ["equipment_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_aa_eszkoz_profilok_equipment_id", table_name="aa_eszkoz_profilok")
    op.drop_table("aa_eszkoz_profilok")
