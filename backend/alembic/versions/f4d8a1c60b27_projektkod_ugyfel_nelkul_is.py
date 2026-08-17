"""Projektkód ügyfél nélkül is felvehető

A projektkód gyakran előbb kell, mint ahogy eldőlne, kinek dolgozunk rajta: a
következő szabad sorszámot lefoglalják, az ügyfél pedig később kerül mellé.
Eddig a felvételhez kötelező volt megrendelőt választani, ezért ilyenkor
valaki egy tetszőleges ügyfelet írt be - amit utána senki nem javított ki.

Ami az ügyfélre épül, kezeli a hiányát: ügyfél nélkül nincs keretszerződés-
fedés, tehát eseti szerződés kell (lásd services/megrendeloi_papir.py).

Revision ID: f4d8a1c60b27
Revises: e2b7c4915d63
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4d8a1c60b27"
down_revision: Union[str, Sequence[str], None] = "e2b7c4915d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("project_codes", "client_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Visszaút csak akkor járható, ha közben nem keletkezett ügyfél nélküli
    # projektkód - ezért nem próbálunk kitalálni nekik egy megrendelőt.
    op.alter_column("project_codes", "client_id", existing_type=sa.Integer(), nullable=False)
