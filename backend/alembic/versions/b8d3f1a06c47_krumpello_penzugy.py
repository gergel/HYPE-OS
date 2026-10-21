"""Krumpello - önálló pénzügyi nyilvántartás

Napi kassza, kiadások (utalás / készpénz / extra), dolgozók és munkaóra.

Miért külön táblák a meglévő expenses/revenues helyett: a Krumpello másik
üzlet, projektkód és ügyfél nélkül. Közös táblában minden HYPE-összesítőben
szűrni kellene rá, és egyetlen kifelejtett szűrő összekeverné a két kasszát
(lásd models/krumpello.py).

Revision ID: b8d3f1a06c47
Revises: a7c2e40b95f1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d3f1a06c47"
down_revision: Union[str, Sequence[str], None] = "a7c2e40b95f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "krumpello_napok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("brutto_kp", sa.Numeric(12, 2), nullable=True, comment="Bruttó bevétel készpénzben"),
        sa.Column("brutto_kartya", sa.Numeric(12, 2), nullable=True, comment="Bruttó bevétel kártyával"),
        sa.Column("netto_kp", sa.Numeric(12, 2), nullable=True, comment="Nettó bevétel készpénzben"),
        sa.Column("netto_kartya", sa.Numeric(12, 2), nullable=True, comment="Nettó bevétel kártyával"),
        sa.Column("borravalo_kp", sa.Numeric(12, 2), nullable=True),
        sa.Column("borravalo_kartya", sa.Numeric(12, 2), nullable=True),
        sa.Column("extra", sa.Numeric(12, 2), nullable=True, comment="Számla nélküli bevétel"),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("datum", name="uq_krumpello_nap_datum"),
    )
    op.create_index(op.f("ix_krumpello_napok_datum"), "krumpello_napok", ["datum"])

    op.create_table(
        "krumpello_kiadasok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forras", sa.String(20), nullable=False, comment="utalas / keszpenz / extra"),
        sa.Column("kedvezmenyezett", sa.String(255), nullable=False, comment="Kinek fizettünk"),
        sa.Column("datum", sa.Date(), nullable=True),
        sa.Column("megnevezes", sa.String(500), nullable=True, comment="Mire ment el"),
        sa.Column("netto", sa.Numeric(12, 2), nullable=True),
        sa.Column("afa", sa.Numeric(12, 2), nullable=True),
        sa.Column("brutto", sa.Numeric(12, 2), nullable=True),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_krumpello_kiadasok_forras"), "krumpello_kiadasok", ["forras"])
    op.create_index(op.f("ix_krumpello_kiadasok_datum"), "krumpello_kiadasok", ["datum"])

    op.create_table(
        "krumpello_dolgozok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nev", sa.String(255), nullable=False),
        sa.Column("alap_orabar", sa.Numeric(12, 2), nullable=True),
        sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "krumpello_munkaorak",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dolgozo_id", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("ora", sa.Numeric(6, 2), nullable=True, comment="Ledolgozott órák száma"),
        sa.Column("orabar", sa.Numeric(12, 2), nullable=True, comment="Az ADOTT napi órabér"),
        sa.Column("fizetes", sa.Numeric(12, 2), nullable=True, comment="A napra járó bér"),
        sa.Column("borravalo", sa.Numeric(12, 2), nullable=True),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["dolgozo_id"], ["krumpello_dolgozok.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_krumpello_munkaorak_dolgozo_id"), "krumpello_munkaorak", ["dolgozo_id"])
    op.create_index(op.f("ix_krumpello_munkaorak_datum"), "krumpello_munkaorak", ["datum"])


def downgrade() -> None:
    op.drop_table("krumpello_munkaorak")
    op.drop_table("krumpello_dolgozok")
    op.drop_table("krumpello_kiadasok")
    op.drop_table("krumpello_napok")
