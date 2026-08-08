"""Kotelezettseg fizetesi mod es netto plusz afa

A kötelezettségek ára és a fordulónkénti tényleges összeg mostantól NETTÓ, és
külön jelöljük, jön-e rá áfa - a bruttót ebből számoljuk (nettó * 1,27, vagy ha
nincs áfa, a kettő ugyanaz), így a két szám sosem mondhat ellent egymásnak.
Emellé bekerül, hogyan fizetjük: átutalással, készpénzzel vagy bankkártyával.


Revision ID: b33c7fe30dfe
Revises: d4a6f86fce3c
Create Date: 2026-08-08 11:13:26.623985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b33c7fe30dfe'
down_revision: Union[str, Sequence[str], None] = 'd4a6f86fce3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kotelezettseg_idoszakok', sa.Column('plusz_afa', sa.Boolean(), server_default='false', nullable=False))
    op.alter_column('kotelezettseg_idoszakok', 'osszeg',
               existing_type=sa.NUMERIC(precision=12, scale=2),
               comment='Nettó összeg',
               existing_nullable=True)
    op.add_column('kotelezettsegek', sa.Column('fizetesi_mod', sa.String(length=50), nullable=True))
    op.add_column('kotelezettsegek', sa.Column('ar_plusz_afa', sa.Boolean(), server_default='false', nullable=False))
    op.alter_column('kotelezettsegek', 'ar_osszeg',
               existing_type=sa.NUMERIC(precision=12, scale=2),
               comment='Nettó ár',
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('kotelezettsegek', 'ar_osszeg',
               existing_type=sa.NUMERIC(precision=12, scale=2),
               comment=None,
               existing_comment='Nettó ár',
               existing_nullable=True)
    op.drop_column('kotelezettsegek', 'ar_plusz_afa')
    op.drop_column('kotelezettsegek', 'fizetesi_mod')
    op.alter_column('kotelezettseg_idoszakok', 'osszeg',
               existing_type=sa.NUMERIC(precision=12, scale=2),
               comment=None,
               existing_comment='Nettó összeg',
               existing_nullable=True)
    op.drop_column('kotelezettseg_idoszakok', 'plusz_afa')
