"""Adminisztráció ellenőrzése: tevékenységnapló, beállítások, kivétel-
jelölések és Lara figyelésének jelzései.

Csak NÉGY ÚJ, üres tábla - meglévő adat nem változik. Lara figyelése alapból
KI van kapcsolva. Visszafordítható.

Revision ID: f6a7d8m9e0l1
Revises: e5p6a7p8i9r0
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7d8m9e0l1"
down_revision = "e5p6a7p8i9r0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_tevekenysegek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letrejott_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("muvelet", sa.String(50), nullable=False),
        sa.Column("targy", sa.String(50), nullable=False),
        sa.Column("leiras", sa.String(300), nullable=False),
        sa.Column("metodus", sa.String(10), nullable=False),
        sa.Column("utvonal", sa.String(300), nullable=False),
        sa.Column("parameterek", sa.JSON()),
        sa.Column("project_id", sa.Integer()),
        sa.Column("adat", sa.JSON()),
    )
    op.create_index("ix_admin_tevekenysegek_letrejott_at", "admin_tevekenysegek", ["letrejott_at"])
    op.create_index("ix_admin_tevekenysegek_ki_mikor", "admin_tevekenysegek", ["employee_id", "letrejott_at"])
    op.create_index("ix_admin_tevekenysegek_muvelet", "admin_tevekenysegek", ["muvelet"])
    op.create_index("ix_admin_tevekenysegek_project_id", "admin_tevekenysegek", ["project_id"])

    op.create_table(
        "admin_ellenorzes_beallitasok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("figyelt_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("lara_figyeles", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hataridok", sa.JSON()),
        sa.Column("utolso_futas_at", sa.DateTime(timezone=True)),
        sa.Column("modositva_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "admin_kivetel_jelolesek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kulcs", sa.String(100), nullable=False),
        sa.Column("dontes", sa.String(20), nullable=False),
        sa.Column("megjegyzes", sa.Text()),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("letrejott_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_kivetel_jelolesek_kulcs", "admin_kivetel_jelolesek", ["kulcs"])

    op.create_table(
        "lara_figyeles_jelzesek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kulcs", sa.String(150), nullable=False, unique=True),
        sa.Column("szabaly", sa.String(50), nullable=False),
        sa.Column("szint", sa.String(20), nullable=False, server_default="figyelem"),
        sa.Column("cim", sa.String(300), nullable=False),
        sa.Column("leiras", sa.Text()),
        sa.Column("link", sa.String(300)),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("adat", sa.JSON()),
        sa.Column("letrejott_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lezarva_at", sa.DateTime(timezone=True)),
        sa.Column("lezarta_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
    )
    op.create_index("ix_lara_figyeles_jelzesek_nyitott", "lara_figyeles_jelzesek", ["lezarva_at"])


def downgrade() -> None:
    op.drop_index("ix_lara_figyeles_jelzesek_nyitott", table_name="lara_figyeles_jelzesek")
    op.drop_table("lara_figyeles_jelzesek")
    op.drop_index("ix_admin_kivetel_jelolesek_kulcs", table_name="admin_kivetel_jelolesek")
    op.drop_table("admin_kivetel_jelolesek")
    op.drop_table("admin_ellenorzes_beallitasok")
    for ix in ("ix_admin_tevekenysegek_project_id", "ix_admin_tevekenysegek_muvelet",
               "ix_admin_tevekenysegek_ki_mikor", "ix_admin_tevekenysegek_letrejott_at"):
        op.drop_index(ix, table_name="admin_tevekenysegek")
    op.drop_table("admin_tevekenysegek")
