"""Krumpello: foglalkoztatási időszakok és a napi bejelentés

A Krumpellóban ugyanaz az ember év közben többféleképpen dolgozik: nyáron
EFO-val, ősztől határozott idejű munkaszerződéssel, közben pedig van nap,
amire egyáltalán nincs bejelentve. Ez dönti el, hogyan kell fizetni: a
bejelentett napi bér utalással megy, a fölötte lévő rész készpénzben.

Két új dolog:

- `krumpello_idoszakok`: egy ember foglalkoztatási időszaka (mettől meddig,
  milyen bejelentéssel, mennyi a bejelentett napi bér). Egyben az elszámolás
  egysége is.
- a munkaóra-soron `bejelentes` + `bejelentett_napi_ber`: naponta felülírható
  kivétel. Üresen az időszakából örökli.

A napokat szándékosan NEM idegen kulcs köti az időszakhoz, hanem a dátum -
lásd models/krumpello.py KrumpelloIdoszak.

Revision ID: d4f8c1a05b73
Revises: c9e4a71b2f08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f8c1a05b73"
down_revision: Union[str, Sequence[str], None] = "c9e4a71b2f08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "krumpello_idoszakok",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dolgozo_id", sa.Integer(), nullable=False),
        sa.Column("kezdet", sa.Date(), nullable=False),
        sa.Column("veg", sa.Date(), nullable=True, comment="Üresen: azóta is tart"),
        sa.Column(
            "bejelentes",
            sa.String(20),
            nullable=False,
            server_default="nincs",
            comment="efo / hatarozott / nincs",
        ),
        sa.Column(
            "napi_ber",
            sa.Numeric(12, 2),
            nullable=True,
            comment="A bejelentett napi bér, ami utalással megy",
        ),
        sa.Column("nev", sa.String(255), nullable=True),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["dolgozo_id"], ["krumpello_dolgozok.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_krumpello_idoszakok_dolgozo_id"), "krumpello_idoszakok", ["dolgozo_id"])
    op.create_index(op.f("ix_krumpello_idoszakok_kezdet"), "krumpello_idoszakok", ["kezdet"])

    op.add_column(
        "krumpello_munkaorak",
        sa.Column("bejelentes", sa.String(20), nullable=True, comment="efo / hatarozott / nincs"),
    )
    op.add_column(
        "krumpello_munkaorak",
        sa.Column(
            "bejelentett_napi_ber",
            sa.Numeric(12, 2),
            nullable=True,
            comment="Az utalással fizetett alap napi bér",
        ),
    )


def downgrade() -> None:
    op.drop_column("krumpello_munkaorak", "bejelentett_napi_ber")
    op.drop_column("krumpello_munkaorak", "bejelentes")
    op.drop_index(op.f("ix_krumpello_idoszakok_kezdet"), table_name="krumpello_idoszakok")
    op.drop_index(op.f("ix_krumpello_idoszakok_dolgozo_id"), table_name="krumpello_idoszakok")
    op.drop_table("krumpello_idoszakok")
