"""Alkalmazotti szuperbrutto a havi belsos bejegyzesen

A bejelentett alkalmazottnál két összeg van, és a kettő NEM ugyanaz: a nettó
bér az, ami az emberhez tartozik ("mennyi a fizetése"), a szuperbruttó pedig a
teljes munkáltatói költség - a kiadások közé ez utóbbi kerül. A szorzót nem
számoljuk (adósáv, kedvezmények, cafeteria), kézzel adja meg, aki a bérlapot
látja.

Revision ID: c41a7f9b2d18
Revises: bb0125472a2e
Create Date: 2026-08-08 10:12:04.113920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41a7f9b2d18'
down_revision: Union[str, Sequence[str], None] = 'bb0125472a2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'internal_performance_certificates',
        sa.Column(
            'szuperbrutto',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment='Bejelentett alkalmazott teljes munkáltatói költsége',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('internal_performance_certificates', 'szuperbrutto')
