"""belsos tig sajat dokumentum tarhely kulcs

A Belsős TIG dokumentuma mostantól kézzel is feltölthető (a hónap oldaláról) -
ilyenkor a fájl a MI tárhelyünkön (R2) van, és törléskor az objektumot is el
kell dobni. A generált, Drive-on maradó PDF-nél ez a mező üres marad.

Revision ID: 1a04224ec881
Revises: 8445b2b6a200
Create Date: 2026-08-05 10:03:50.778888

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a04224ec881'
down_revision: Union[str, Sequence[str], None] = '8445b2b6a200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "internal_performance_certificates",
        sa.Column("file_storage_key", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("internal_performance_certificates", "file_storage_key")
