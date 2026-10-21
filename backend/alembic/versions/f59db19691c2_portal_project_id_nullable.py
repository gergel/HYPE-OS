"""portal project_id nullable

Revision ID: f59db19691c2
Revises: 4976883a7987
Create Date: 2026-07-06 21:40:40.256008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f59db19691c2'
down_revision: Union[str, Sequence[str], None] = '4976883a7987'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("portals", "project_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("portals", "project_id", existing_type=sa.Integer(), nullable=False)
