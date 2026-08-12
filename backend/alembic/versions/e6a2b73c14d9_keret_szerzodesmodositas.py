"""Megrendelői keretszerződés: szerződésmódosítások

Egy keretszerződést az évek alatt többször is módosítanak (székhely,
cégjegyzékszám, díjazás), és mindegyik módosítás önálló papír: saját
keltezéssel, kiküldéssel és aláírt példánnyal. Ezért külön tábla, nem néhány
mező a `contracts`-on - egyetlen `modositas_file_url` a másodiknál felülírná
az elsőt.

A cégadatok MÁSOLATBAN kerülnek a sorra: a papír azt őrzi, ami rajta van
(lásd models/keret_modositas.py).

Revision ID: e6a2b73c14d9
Revises: d4f8c1a05b73
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6a2b73c14d9"
down_revision: Union[str, Sequence[str], None] = "d4f8c1a05b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "keret_modositasok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("ceg_neve", sa.String(length=255), nullable=True),
        sa.Column("szekhely", sa.String(length=500), nullable=True),
        sa.Column("adoszam", sa.String(length=50), nullable=True),
        sa.Column("kepviselo", sa.String(length=255), nullable=True),
        sa.Column("nyilvantartasi_szam", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("keltezes", sa.Date(), nullable=True),
        sa.Column("allapot", sa.String(length=50), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("file_storage_key", sa.String(length=500), nullable=True),
        sa.Column("alairt_file_url", sa.String(length=500), nullable=True),
        sa.Column("alairt_file_storage_key", sa.String(length=500), nullable=True),
        sa.Column("kikuldve", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kikuldte_id", sa.Integer(), nullable=True),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kikuldte_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_keret_modositasok_contract_id", "keret_modositasok", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_keret_modositasok_contract_id", table_name="keret_modositasok")
    op.drop_table("keret_modositasok")
