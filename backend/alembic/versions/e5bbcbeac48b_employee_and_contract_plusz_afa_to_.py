"""employee and contract plusz_afa to boolean

Revision ID: e5bbcbeac48b
Revises: 79fd22f33301
Create Date: 2026-07-07 07:59:32.546014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5bbcbeac48b'
down_revision: Union[str, Sequence[str], None] = '79fd22f33301'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TO_BOOL_USING = (
    "CASE WHEN plusz_afa IS NULL THEN NULL "
    "WHEN lower(plusz_afa) IN ('igen', 'yes', 'true', '1') THEN true "
    "ELSE false END"
)
_TO_STRING_USING = "CASE WHEN plusz_afa IS NULL THEN NULL WHEN plusz_afa THEN 'Igen' ELSE 'Nem' END"


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "employees",
        "plusz_afa",
        existing_type=sa.String(length=100),
        type_=sa.Boolean(),
        postgresql_using=_TO_BOOL_USING,
        existing_comment="Plusz ÁFA",
        existing_nullable=True,
    )
    op.alter_column(
        "contracts",
        "plusz_afa",
        existing_type=sa.String(length=50),
        type_=sa.Boolean(),
        postgresql_using=_TO_BOOL_USING,
        existing_comment="Plusz ÁFA",
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "contracts",
        "plusz_afa",
        existing_type=sa.Boolean(),
        type_=sa.String(length=50),
        postgresql_using=_TO_STRING_USING,
        existing_comment="Plusz ÁFA",
        existing_nullable=True,
    )
    op.alter_column(
        "employees",
        "plusz_afa",
        existing_type=sa.Boolean(),
        type_=sa.String(length=100),
        postgresql_using=_TO_STRING_USING,
        existing_comment="Plusz ÁFA",
        existing_nullable=True,
    )
