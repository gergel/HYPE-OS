"""Krumpello munkabér: kifizetve jelölés

Napi bontásban jelöljük, mit fizettünk már ki - a kifizetés a gyakorlatban
időszakonként történik (lásd a kassza-táblázat "ZÁRÁS" sorait), de a jelölés
soronként kerül fel, hogy egy utólag hozzáírt nap ne látszódjon automatikusan
kifizetettnek (lásd models/krumpello.py).

A meglévő sorok `kifizetve = false` értékkel indulnak. Ez SZÁNDÉKOS: a
betöltött történeti adatból nem derül ki, mit utaltak el ténylegesen - a
"ZÁRÁS" sorok ugyan összegeznek, de nem mondják meg, hogy meg is történt-e. A
hamis "kifizetve" rosszabb, mint a jelöletlen: az egyik miatt elmarad egy
utalás, a másik miatt csak egyszer rá kell nézni.

Revision ID: d9a4c73b1e52
Revises: c5b71e29d840
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9a4c73b1e52"
down_revision: Union[str, Sequence[str], None] = "c5b71e29d840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "krumpello_munkaorak",
        sa.Column("kifizetve", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("krumpello_munkaorak", sa.Column("kifizetes_datuma", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("krumpello_munkaorak", "kifizetes_datuma")
    op.drop_column("krumpello_munkaorak", "kifizetve")
