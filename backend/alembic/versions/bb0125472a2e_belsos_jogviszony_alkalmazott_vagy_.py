"""Belsos jogviszony: alkalmazott vagy megbizasi

A bejelentett alkalmazottól nincs havi TIG (a bérét bérszámfejtés fizeti) - a
havi teendő nála csak annyi, hogy a fizetése be legyen írva. Az alapértelmezés
a "megbizas": ez a rendszer eddigi viselkedése, tehát a mező bevezetése
önmagában senkinél nem változtat semmit.

Revision ID: bb0125472a2e
Revises: bf20f2bb43e7
Create Date: 2026-08-08 08:23:41.691666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb0125472a2e'
down_revision: Union[str, Sequence[str], None] = 'bf20f2bb43e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # A PostgreSQL enum típust KÜLÖN kell létrehozni: az op.add_column - a
    # create_table-lel ellentétben - nem hozza létre magától, és a migráció
    # "type does not exist" hibával állna meg.
    jogviszony = sa.Enum('megbizas', 'alkalmazott', name='belsos_jogviszony')
    jogviszony.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'employees',
        sa.Column('belsos_jogviszony', jogviszony, server_default='megbizas', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('employees', 'belsos_jogviszony')
    # A PostgreSQL enum típus nem törlődik az oszloppal - kézzel kell.
    sa.Enum(name='belsos_jogviszony').drop(op.get_bind(), checkfirst=True)
