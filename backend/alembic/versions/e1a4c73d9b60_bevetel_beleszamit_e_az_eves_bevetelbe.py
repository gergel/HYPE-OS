"""Bevétel: beleszámít-e az éves bevételbe

Van bevétel-sor, ami látszani akar (a projekt profitja miatt), de az éves
bevételbe nem való: nem volt tranzakció, vagy a munka másképp lett rendezve
(beszámítás, csere, másik cégen át). A kiadás-oldali
`hozzaadas_a_kiadasokhoz` párja, ugyanazzal a szabállyal: NULL = beleszámít,
hogy a régi sorok ne tűnjenek el némán az összesítőkből.

Revision ID: e1a4c73d9b60
Revises: d7f2a94c1e05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.migracio import zarasbiztos_ddl

revision: str = "e1a4c73d9b60"
down_revision: Union[str, Sequence[str], None] = "d7f2a94c1e05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SZÁNDÉKOSAN nullable, server_default nélkül: a NULL itt jelentést hordoz
    # ("nem mondtunk róla semmit" = beleszámít), és így a több százezer régi
    # sort nem kell átírni a deploy alatt.
    zarasbiztos_ddl(
        op,
        lambda: op.add_column(
            "revenues",
            sa.Column(
                "beleszamit_a_bevetelekbe",
                sa.Boolean(),
                nullable=True,
                comment="Beleszámít-e az éves bevételbe (NULL = igen)",
            ),
        ),
        leiras="revenues.beleszamit_a_bevetelekbe",
    )


def downgrade() -> None:
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("revenues", "beleszamit_a_bevetelekbe"),
        leiras="revenues.beleszamit_a_bevetelekbe (törlés)",
    )
