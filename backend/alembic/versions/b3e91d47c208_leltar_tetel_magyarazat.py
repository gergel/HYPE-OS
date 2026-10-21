"""Leltár-tétel magyarázata (miért szerelendő / miért van szervizben)

A leltár lezárása ezentúl megköveteli: a "Szerelendő" és a "Szervíz" állapotú
eszközökhöz oda kell írni, mi a bajuk. Egy hónappal később a puszta státuszból
már senki nem tudja, mi történt a géppel és hol van - a leltározás viszont épp
az a pillanat, amikor ezt valaki még fejből tudja.

Revision ID: b3e91d47c208
Revises: a8c2f75e1d94
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.migracio import zarasbiztos_ddl

revision: str = "b3e91d47c208"
down_revision: Union[str, Sequence[str], None] = "a8c2f75e1d94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Zárolás-biztosan: a deploy alatt a régi példány még olvassa a táblát
    # (lásd app/core/migracio.py).
    zarasbiztos_ddl(
        op,
        lambda: op.add_column("stocktake_items", sa.Column("megjegyzes", sa.Text(), nullable=True)),
        leiras="stocktake_items.megjegyzes",
    )


def downgrade() -> None:
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("stocktake_items", "megjegyzes"),
        leiras="stocktake_items.megjegyzes (törlés)",
    )
