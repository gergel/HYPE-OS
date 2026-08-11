"""Vágói játék: fotó a nyereményről

Egy kép többet mond, mint a "20 000 Ft utalvány" - a verseny attól megy, hogy
LÁTJÁK, miért mennek.

A storage-kulcs azért van a URL mellett, mert csere/törléskor a régi
objektumot is el kell dobni a tárhelyről, és a publikus URL-ből ez nem mindig
fejthető vissza (lásd services/document_storage.py).

Revision ID: f3b8d05e7a91
Revises: e6f2a91c4d73
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3b8d05e7a91"
down_revision: Union[str, Sequence[str], None] = "e6f2a91c4d73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vago_jatek_honapok", sa.Column("kep_url", sa.String(500), nullable=True))
    op.add_column("vago_jatek_honapok", sa.Column("kep_storage_key", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("vago_jatek_honapok", "kep_storage_key")
    op.drop_column("vago_jatek_honapok", "kep_url")
