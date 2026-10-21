"""Utalások felvezetése: kétlépcsős folyamat (besorolás jóváhagyása + rögzítés).

Új tétel-mezők: elszamolas_megerositve (a HYPE/Krumpelló besorolást ember
erősítette meg), besorolas_jovahagyva + jovahagyo + jovahagyva_at (a cél
elfogadása - a rögzítés csak jóváhagyott tételen fut). Lásd
models/utalas_felvezetes.py és services/utalas_felvezetes.py.

Revision ID: v9n6m07j4l28
Revises: u8m5l96i3k17
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "v9n6m07j4l28"
down_revision = "u8m5l96i3k17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "utalas_tetelek",
        sa.Column("elszamolas_megerositve", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "utalas_tetelek",
        sa.Column("besorolas_jovahagyva", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "utalas_tetelek",
        sa.Column("jovahagyo_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
    )
    op.add_column("utalas_tetelek", sa.Column("jovahagyva_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("utalas_tetelek", "jovahagyva_at")
    op.drop_column("utalas_tetelek", "jovahagyo_employee_id")
    op.drop_column("utalas_tetelek", "besorolas_jovahagyva")
    op.drop_column("utalas_tetelek", "elszamolas_megerositve")
