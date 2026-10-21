"""Szuperbrutto visszavonasa

A bejelentett alkalmazottnál mégsem kell a szuperbruttó: a havi teendő
egyetlen szám, a nettó bér. Az oszlopot ezért elvisszük.

Nem a bevezető migráció (c41a7f9b2d18) törlésével, hanem külön lépésben: ha az
már lefutott valahol, egy eltűnt revízióra az alembic "Can't locate revision"
hibával állna meg.

Revision ID: d7c2e4a91b60
Revises: c41a7f9b2d18
Create Date: 2026-08-08 11:47:52.204318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7c2e4a91b60'
down_revision: Union[str, Sequence[str], None] = 'c41a7f9b2d18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('internal_performance_certificates', 'szuperbrutto')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'internal_performance_certificates',
        sa.Column(
            'szuperbrutto',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment='Bejelentett alkalmazott teljes munkáltatói költsége',
        ),
    )
