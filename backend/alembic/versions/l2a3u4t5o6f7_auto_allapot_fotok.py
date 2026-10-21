"""Autó állapotfotók: bekérő link és fotók.

A felhasználó kérése: az autók állapotáról linken keresztül lehessen fotókat
bekérni (7 nézet), és autónként visszanézhető legyen, melyik nap milyen kép
készült. Két új, üres tábla - meglévő adat nem változik. Visszafordítható.

Revision ID: l2a3u4t5o6f7
Revises: k1f2e3l4t5o6
"""

import sqlalchemy as sa
from alembic import op

revision = "l2a3u4t5o6f7"
down_revision = "k1f2e3l4t5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_allapot_bekeresek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auto_id", sa.Integer(), sa.ForeignKey("autok.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("letrehozta_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("letrejott_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("visszavonva_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auto_allapot_bekeresek_auto_id", "auto_allapot_bekeresek", ["auto_id"])
    op.create_index("ix_auto_allapot_bekeresek_token", "auto_allapot_bekeresek", ["token"], unique=True)
    op.create_table(
        "auto_allapot_fotok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auto_id", sa.Integer(), sa.ForeignKey("autok.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bekeres_id", sa.Integer(), sa.ForeignKey("auto_allapot_bekeresek.id", ondelete="SET NULL")),
        sa.Column("oldal", sa.String(length=30), nullable=False),
        sa.Column("keszult_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("keszito", sa.String(length=120)),
        sa.Column("kulcs", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("belyeg_kulcs", sa.String(length=500)),
        sa.Column("belyeg_url", sa.String(length=500)),
        sa.Column("meret", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_auto_allapot_fotok_auto_id", "auto_allapot_fotok", ["auto_id"])
    op.create_index("ix_auto_allapot_fotok_bekeres_id", "auto_allapot_fotok", ["bekeres_id"])
    op.create_index("ix_auto_allapot_fotok_keszult_at", "auto_allapot_fotok", ["keszult_at"])


def downgrade() -> None:
    op.drop_table("auto_allapot_fotok")
    op.drop_table("auto_allapot_bekeresek")
