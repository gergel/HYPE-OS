"""Számla-lépés: kifizetve, de ne kerüljön a bevételek közé

A megrendelői számla lezárásakor alapból bevétel-sor keletkezik. Van viszont
olyan munka, ami ki van fizetve, de a Pénzügyekbe nem való (beszámították,
máshol könyvelték) - ilyenkor a projektkód mégis lezárt, csak indokkal.

Revision ID: c5d18b3f2a76
Revises: b3e91d47c208
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.migracio import zarasbiztos_ddl

revision: str = "c5d18b3f2a76"
down_revision: Union[str, Sequence[str], None] = "b3e91d47c208"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Zárolás-biztosan: a deploy alatt a régi példány még olvassa a táblát
    # (lásd app/core/migracio.py).
    zarasbiztos_ddl(
        op,
        lambda: op.add_column(
            "project_codes",
            sa.Column("bevetelbe_ne_keruljon", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        leiras="project_codes.bevetelbe_ne_keruljon",
    )
    zarasbiztos_ddl(
        op,
        lambda: op.add_column("project_codes", sa.Column("bevetel_kihagyas_oka", sa.Text(), nullable=True)),
        leiras="project_codes.bevetel_kihagyas_oka",
    )


def downgrade() -> None:
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("project_codes", "bevetel_kihagyas_oka"),
        leiras="project_codes.bevetel_kihagyas_oka (törlés)",
    )
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("project_codes", "bevetelbe_ne_keruljon"),
        leiras="project_codes.bevetelbe_ne_keruljon (törlés)",
    )
