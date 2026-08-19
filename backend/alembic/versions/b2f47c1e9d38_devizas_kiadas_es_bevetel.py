"""Devizás kiadás és bevétel: az eredeti pénznem és összeg megőrzése

A `netto`/`brutto` mindig forint marad - ezek az oszlopok azt őrzik, MIBŐL lett
(lásd services/penznem.py). Az `arfolyam` oszlop mindkét táblán már megvolt
(Notionből örökölt), azt használjuk.

Revision ID: b2f47c1e9d38
Revises: e1a4c73d9b60
"""

import sqlalchemy as sa
from alembic import op

revision = "b2f47c1e9d38"
down_revision = "e1a4c73d9b60"
branch_labels = None
depends_on = None

TABLAK = ("expenses", "revenues")


def upgrade() -> None:
    for tabla in TABLAK:
        op.add_column(
            tabla,
            sa.Column(
                "eredeti_penznem",
                sa.String(length=10),
                nullable=True,
                comment="Milyen pénznemben vezették fel (NULL = forintban)",
            ),
        )
        op.add_column(
            tabla,
            sa.Column(
                "eredeti_netto",
                sa.Numeric(precision=12, scale=2),
                nullable=True,
                comment="A nettó az eredeti pénznemben",
            ),
        )
        op.add_column(
            tabla,
            sa.Column(
                "eredeti_brutto",
                sa.Numeric(precision=12, scale=2),
                nullable=True,
                comment="A bruttó az eredeti pénznemben",
            ),
        )


def downgrade() -> None:
    for tabla in TABLAK:
        op.drop_column(tabla, "eredeti_brutto")
        op.drop_column(tabla, "eredeti_netto")
        op.drop_column(tabla, "eredeti_penznem")
