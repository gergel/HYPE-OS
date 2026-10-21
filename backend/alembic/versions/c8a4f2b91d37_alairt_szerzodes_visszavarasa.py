"""aláírt szerződés visszavárása

A kiküldött szerződés még nem lezárt ügy: várjuk vissza aláírva. Eddig ennek
nem volt helye - a `szerzodes_file_url` a MI dokumentumunkat tartja (generált
vagy feltöltött), nem a visszaérkező, aláírt példányt.

Két új oszlop a visszaérkező papírnak. Az `alairva` jelölő már megvolt, azt
állítja be a feltöltés.

Revision ID: c8a4f2b91d37
Revises: b3c71a5d8e02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8a4f2b91d37"
down_revision: Union[str, Sequence[str], None] = "b3c71a5d8e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("alairt_file_url", sa.String(length=500), nullable=True))
    op.add_column("contracts", sa.Column("alairt_file_storage_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("contracts", "alairt_file_storage_key")
    op.drop_column("contracts", "alairt_file_url")
