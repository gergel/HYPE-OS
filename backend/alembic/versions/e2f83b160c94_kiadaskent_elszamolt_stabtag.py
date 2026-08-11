"""projekt kiadásként elszámolt stábtag

Van, aki ott volt a forgatáson, de nem résztvevőként számoljuk el: pl. technikát
hozott, és a díja a bérleti árban már benne van. Neki nem kell sem szerződés,
sem teljesítési igazolás - a költségét egy projekt kiadás fedezi.

A jelölő a (projekt, ember) páron él, a számlázó fél felülírása mellett: ez a
tábla éli túl a stáblista szerkesztését (lásd models/project_szamlazo.py
osztály-kommentje).

Revision ID: e2f83b160c94
Revises: d5e91c74a3b8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f83b160c94"
down_revision: Union[str, Sequence[str], None] = "d5e91c74a3b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_szamlazok",
        sa.Column("kiadaskent_elszamolva", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("project_szamlazok", "kiadaskent_elszamolva", server_default=None)


def downgrade() -> None:
    op.drop_column("project_szamlazok", "kiadaskent_elszamolva")
