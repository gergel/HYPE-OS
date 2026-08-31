"""A projekt helyszín mezője többsoros (Text, mint a brief).

A felhasználó kérése: a diszpónál a helyszínbe több dolgot is fel lehessen
írni egymás alá - a felület a Text oszlopokat automatikusan többsoros
szerkesztőként kezeli (lásd services/entity_registry.mezotipus).

Revision ID: d2e8b47f9a31
Revises: c1f7a83e6d29
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "d2e8b47f9a31"
down_revision = "c1f7a83e6d29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("projects", "helyszin", type_=sa.Text(), existing_type=sa.String(length=255))


def downgrade() -> None:
    op.alter_column("projects", "helyszin", type_=sa.String(length=255), existing_type=sa.Text())
