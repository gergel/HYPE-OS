"""Vágói játék - havi pontverseny

Havi nyeremény, emberenkénti munkanap (az arányosításhoz) és az
"ellenőrzésbe került" események naplója.

Az esemény-tábla azért kell, mert a pont a MEGTÖRTÉNT eseményhez tartozik,
nem az anyag mai állapotához: egy későbbi állapotváltás különben
visszamenőleg elvenné a pontot, egy oda-vissza kattintgatás pedig újra és újra
adná (lásd models/vagoi_jatek.py).

Revision ID: e6f2a91c4d73
Revises: d9a4c73b1e52
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f2a91c4d73"
down_revision: Union[str, Sequence[str], None] = "d9a4c73b1e52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vago_jatek_honapok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ev", sa.Integer(), nullable=False),
        sa.Column("honap", sa.Integer(), nullable=False),
        sa.Column("nyeremeny", sa.String(255), nullable=True),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ev", "honap", name="uq_vago_jatek_honap"),
    )

    op.create_table(
        "vago_jatek_napok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ev", sa.Integer(), nullable=False),
        sa.Column("honap", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("munkanap", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ev", "honap", "employee_id", name="uq_vago_jatek_nap"),
    )
    op.create_index(op.f("ix_vago_jatek_napok_employee_id"), "vago_jatek_napok", ["employee_id"])

    op.create_table(
        "vago_ellenorzes_esemenyek",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deliverable_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("idopont", sa.DateTime(timezone=True), nullable=False),
        sa.Column("allapot", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deliverable_id", name="uq_vago_ellenorzes_deliverable"),
    )
    op.create_index(op.f("ix_vago_ellenorzes_esemenyek_employee_id"), "vago_ellenorzes_esemenyek", ["employee_id"])
    op.create_index(op.f("ix_vago_ellenorzes_esemenyek_idopont"), "vago_ellenorzes_esemenyek", ["idopont"])


def downgrade() -> None:
    op.drop_table("vago_ellenorzes_esemenyek")
    op.drop_table("vago_jatek_napok")
    op.drop_table("vago_jatek_honapok")
