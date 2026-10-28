"""Utómunka határidejének pontos időpontja (óra:perc).

A felhasználó kérése: az utómunka határidejét ne csak napra lehessen megadni,
hanem bekapcsolhatóan percre pontosan is. Új, üres, nem kötelező oszlop - a
meglévő (csak dátumos) határidők nem változnak. Visszafordítható.

Revision ID: n4h5a6t7i8d9
Revises: n4f5e6l7v8z9
"""

import sqlalchemy as sa
from alembic import op

revision = "n4h5a6t7i8d9"
down_revision = "n4f5e6l7v8z9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliverables", sa.Column("hatarido_ido", sa.Time(), nullable=True, comment="Határidő időpontja"))


def downgrade() -> None:
    op.drop_column("deliverables", "hatarido_ido")
