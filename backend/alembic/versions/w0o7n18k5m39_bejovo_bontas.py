"""Beérkező számlák: több-projektes bontás + automatikus érkeztetés.

Új bejovo_szamlak.bontas JSON oszlop: egy számla több hozzárendelési sora
(projekt/működési cél, meglévő tétel vagy új kiadás, összeg) - a számla egy
pénzügyi dokumentum marad, a bontás nem sokszorozza az összegét. Lásd
models/bejovo_szamla.py és services/szamla_erkeztetes._rogzit_bontaskent.

Revision ID: w0o7n18k5m39
Revises: v9n6m07j4l28
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "w0o7n18k5m39"
down_revision = "v9n6m07j4l28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bejovo_szamlak", sa.Column("bontas", sa.JSON()))


def downgrade() -> None:
    op.drop_column("bejovo_szamlak", "bontas")
