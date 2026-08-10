"""Vagoi visszajelzes kesz anyag link es diszpo kikuldes

A visszajelzésre RÁMÁSOLJUK a kész anyag linkjét (az anyagé később változhat,
a visszajelzésnek viszont évek múlva is arra kell mutatnia, amiről szólt), és
eltesszük, mikor ment ki a forgatás diszpó-levelére válaszként.


Revision ID: 3cc1e9db18b8
Revises: b33c7fe30dfe
Create Date: 2026-08-10 04:58:11.651778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cc1e9db18b8'
down_revision: Union[str, Sequence[str], None] = 'b33c7fe30dfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('feedbacks', sa.Column('kesz_anyag_url', sa.String(length=500), nullable=True))
    op.add_column('feedbacks', sa.Column('diszpora_kikuldve', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('feedbacks', 'diszpora_kikuldve')
    op.drop_column('feedbacks', 'kesz_anyag_url')
