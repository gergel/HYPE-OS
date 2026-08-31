"""Vágói játék: a hónap kihirdetett győztese.

Hónapváltáskor a rendszer magától kihirdeti az előző hónap győztesét
(lásd services/vagoi_jatek.havi_zaras) - itt kap helyet a győztes, a
pontszáma és a kihirdetés időpontja a hónap során.

Revision ID: b8c4f61d2e93
Revises: a7d9e35c1f82
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c4f61d2e93"
down_revision = "a7d9e35c1f82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vago_jatek_honapok", sa.Column("gyoztes_employee_id", sa.Integer(), nullable=True))
    op.add_column("vago_jatek_honapok", sa.Column("gyoztes_pont", sa.Integer(), nullable=True))
    op.add_column("vago_jatek_honapok", sa.Column("kihirdetve_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_vago_jatek_honapok_gyoztes",
        "vago_jatek_honapok",
        "employees",
        ["gyoztes_employee_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_vago_jatek_honapok_gyoztes", "vago_jatek_honapok", type_="foreignkey")
    op.drop_column("vago_jatek_honapok", "kihirdetve_at")
    op.drop_column("vago_jatek_honapok", "gyoztes_pont")
    op.drop_column("vago_jatek_honapok", "gyoztes_employee_id")
