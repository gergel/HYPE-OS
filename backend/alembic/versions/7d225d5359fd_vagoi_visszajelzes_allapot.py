"""Vagoi visszajelzes allapot

Uj | Kikuldve | Nem kuldjuk ki. A mar kikuldott sorok visszamenoleg is a
helyes allapotot kapjak (a kikuldes idopontjabol latszik, hogy megtortent) -
enelkul minden regi visszajelzes "ujkent" allna a listan.


Revision ID: 7d225d5359fd
Revises: 3cc1e9db18b8
Create Date: 2026-08-10 05:35:00.288971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d225d5359fd'
down_revision: Union[str, Sequence[str], None] = '3cc1e9db18b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('feedbacks', sa.Column('allapot', sa.String(length=20), server_default='uj', nullable=False))
    # Amit korábban már kiküldtünk, az ne "új"-ként jelenjen meg.
    op.execute("UPDATE feedbacks SET allapot = 'kikuldve' WHERE diszpora_kikuldve IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('feedbacks', 'allapot')
