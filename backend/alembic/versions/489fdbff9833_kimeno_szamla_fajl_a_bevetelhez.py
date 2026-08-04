"""kimeno szamla fajl a bevetelhez

Revision ID: 489fdbff9833
Revises: 0595066166d9
A megrendelői (KIMENŐ) számla PDF-je feltölthető a bevétel-sorhoz, hogy a
havi számla-csomag (routes/finance.py szamlak_zip) ne csak a bejövő, hanem a
kimenő számlákat is tartalmazza. Maga a számla továbbra is külső számlázó
rendszerben készül - itt csak a fájl és a kiállítás dátuma van.

Create Date: 2026-08-04 11:20:29.999861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '489fdbff9833'
down_revision: Union[str, Sequence[str], None] = '0595066166d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "revenues",
        sa.Column("szamla_filename", sa.String(length=255), nullable=True, comment="A feltöltött kimenő számla fájlneve"),
    )
    op.add_column("revenues", sa.Column("szamla_storage_key", sa.String(length=500), nullable=True))
    op.add_column("revenues", sa.Column("szamla_file_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("revenues", "szamla_file_url")
    op.drop_column("revenues", "szamla_storage_key")
    op.drop_column("revenues", "szamla_filename")
