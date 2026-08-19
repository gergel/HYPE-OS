"""Projektkód: "erről a munkáról nincs számla" (indokkal)

Van, amit nem a megszokott módon fizetnek: nincs kiállított számla, tehát
fizetési határidő sincs - a pénz viszont megjött. A számla-lépés ilyenkor is
lezárható, csak a határidőt nem kérjük számon.

Revision ID: d7f2a94c1e05
Revises: c5d18b3f2a76
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.migracio import zarasbiztos_ddl

revision: str = "d7f2a94c1e05"
down_revision: Union[str, Sequence[str], None] = "c5d18b3f2a76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Zárolás-biztosan: a deploy alatt a régi példány még olvassa a táblát
    # (lásd app/core/migracio.py).
    zarasbiztos_ddl(
        op,
        lambda: op.add_column(
            "project_codes",
            sa.Column("szamla_kihagyva", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        leiras="project_codes.szamla_kihagyva",
    )
    zarasbiztos_ddl(
        op,
        lambda: op.add_column("project_codes", sa.Column("szamla_kihagyas_oka", sa.Text(), nullable=True)),
        leiras="project_codes.szamla_kihagyas_oka",
    )


def downgrade() -> None:
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("project_codes", "szamla_kihagyas_oka"),
        leiras="project_codes.szamla_kihagyas_oka (törlés)",
    )
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("project_codes", "szamla_kihagyva"),
        leiras="project_codes.szamla_kihagyva (törlés)",
    )
