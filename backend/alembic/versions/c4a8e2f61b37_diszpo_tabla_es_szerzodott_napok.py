"""diszpo tabla (HYPE 2026 munkalapok) + belsos szerzodott napok

Revision ID: c4a8e2f61b37
Revises: b3f7c1d92a04
Create Date: 2026-08-21 14:00:00.000000

A Google Sheet "HYPE 2026" táblázata átkerül a rendszerbe: munkalapok, sorok,
oszlopok és cellák - a cellák SZÍNÉVEL együtt, mert ott a szín az adat (ki
melyik nap dolgozott). Lásd models/diszpo_tabla.py.

Mellette a belsős munkatárs két új mezője: hány napra van szerződve egy
hónapban, és mennyi a szerződött napokon felüli nap díja.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a8e2f61b37"
down_revision: Union[str, Sequence[str], None] = "b3f7c1d92a04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "diszpo_munkalapok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nev", sa.String(length=100), nullable=False),
        sa.Column("sorrend", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sor_szam", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("oszlop_szam", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fejlec_sorok", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diszpo_munkalapok_nev"), "diszpo_munkalapok", ["nev"], unique=True)

    op.create_table(
        "diszpo_oszlopok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("munkalap_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("cimke", sa.String(length=255), nullable=True),
        sa.Column("csoport", sa.String(length=100), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["munkalap_id"], ["diszpo_munkalapok.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("munkalap_id", "idx", name="uq_diszpo_oszlop"),
    )
    op.create_index(op.f("ix_diszpo_oszlopok_munkalap_id"), "diszpo_oszlopok", ["munkalap_id"])
    op.create_index(op.f("ix_diszpo_oszlopok_employee_id"), "diszpo_oszlopok", ["employee_id"])

    op.create_table(
        "diszpo_sorok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("munkalap_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=True),
        sa.Column("nap", sa.String(length=20), nullable=True),
        sa.Column("diszposzam", sa.Integer(), nullable=True),
        sa.Column("elvalaszto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["munkalap_id"], ["diszpo_munkalapok.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("munkalap_id", "idx", name="uq_diszpo_sor"),
    )
    op.create_index(op.f("ix_diszpo_sorok_munkalap_id"), "diszpo_sorok", ["munkalap_id"])
    op.create_index(op.f("ix_diszpo_sorok_datum"), "diszpo_sorok", ["datum"])

    op.create_table(
        "diszpo_cellak",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("munkalap_id", sa.Integer(), nullable=False),
        sa.Column("sor_idx", sa.Integer(), nullable=False),
        sa.Column("oszlop_idx", sa.Integer(), nullable=False),
        sa.Column("ertek", sa.Text(), nullable=True),
        sa.Column("szin", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["munkalap_id"], ["diszpo_munkalapok.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("munkalap_id", "sor_idx", "oszlop_idx", name="uq_diszpo_cella"),
    )
    op.create_index(op.f("ix_diszpo_cellak_munkalap_id"), "diszpo_cellak", ["munkalap_id"])
    op.create_index(op.f("ix_diszpo_cellak_szin"), "diszpo_cellak", ["szin"])

    op.add_column("employees", sa.Column("szerzodott_napok", sa.Integer(), nullable=True))
    op.add_column("employees", sa.Column("plusz_nap_napi_dij", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("employees", "plusz_nap_napi_dij")
    op.drop_column("employees", "szerzodott_napok")
    op.drop_table("diszpo_cellak")
    op.drop_table("diszpo_sorok")
    op.drop_table("diszpo_oszlopok")
    op.drop_table("diszpo_munkalapok")
