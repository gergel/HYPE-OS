"""notion import: a helyben módosított mezők védelme

A notion_import_map két új oszlopot kap: mit írt bele legutóbb az import
(imported_fields), és mikor (last_imported_at). Ebből tudja az import
eldönteni, hogy egy mezőt azóta a HYPE OS-ben átírtak-e - ha igen, nem írja
felül (lásd notion_import/engine.py).

A meglévő sorokban az imported_fields NULL marad. Ez szándékos: ott nincs
referenciapontunk, ezért a motor a kitöltött mezőket védettnek tekinti, és
csak az üreseket tölti ki - a lehető legóvatosabb viselkedés.

Revision ID: b3c71a5d8e02
Revises: 634f6e438c87
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c71a5d8e02"
down_revision: Union[str, Sequence[str], None] = "634f6e438c87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notion_import_map", sa.Column("imported_fields", sa.JSON(), nullable=True))
    op.add_column("notion_import_map", sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("notion_import_map", "last_imported_at")
    op.drop_column("notion_import_map", "imported_fields")
