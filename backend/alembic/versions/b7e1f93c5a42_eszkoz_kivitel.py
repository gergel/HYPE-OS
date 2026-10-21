"""Eszközkivitel: eszkoz_kivitelek + eszkoz_kivitel_tetelek táblák.

A felhasználó kérése: bejelentkezés nélküli, 6 jegyű kódos eszközkiviteli
oldal + bejelentkezett kezelő oldal - lásd models/eszkoz_kivitel.py.

Revision ID: b7e1f93c5a42
Revises: a5d9c27e4b31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7e1f93c5a42"
down_revision = "a5d9c27e4b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eszkoz_kivitelek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("kod", sa.String(length=12), nullable=False, unique=True),
        sa.Column("teszt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "eszkoz_kivitel_tetelek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "kivitel_id", sa.Integer(), sa.ForeignKey("eszkoz_kivitelek.id"), nullable=False, index=True
        ),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("kivitt_db", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visszahozott_db", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("kivitel_id", "equipment_id", name="uq_kivitel_eszkoz"),
    )


def downgrade() -> None:
    op.drop_table("eszkoz_kivitel_tetelek")
    op.drop_table("eszkoz_kivitelek")
