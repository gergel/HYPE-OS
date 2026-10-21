"""Szerződésmódosítás: a kiküldött levél szövege

A módosításnál a kísérőlevelet a felhasználó írja meg a kiküldés előtt (nem egy
fix sablonszöveg megy ki), ezért el is tesszük: fél év múlva az a kérdés, hogy
MIT írtunk nekik, nem csak az, hogy küldtünk-e valamit.

Revision ID: f1b8c2e40a67
Revises: e6a2b73c14d9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1b8c2e40a67"
down_revision: Union[str, Sequence[str], None] = "e6a2b73c14d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("keret_modositasok", sa.Column("level_szoveg", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("keret_modositasok", "level_szoveg")
