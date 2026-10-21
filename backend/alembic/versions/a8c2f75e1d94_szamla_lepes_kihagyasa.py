"""Külsős TIG: a számla-lépés kihagyható, indokkal

Van, amikor a TIG elkészült, de a pénz útja itt nem folytatódik: máshol
számolták el, elengedték, beszámították. Eddig az ilyen munkák örökre "nincs
kifizetve" állapotban lógtak az utókövetésben, és a projekt sosem lett kész -
pedig nem volt rajta teendő. Ugyanaz a kihagyás-indok páros, mint a
szerződésnél és magánál a TIG-nél (lásd models/performance_certificate.py).

Revision ID: a8c2f75e1d94
Revises: f4d8a1c60b27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.migracio import zarasbiztos_ddl

revision: str = "a8c2f75e1d94"
down_revision: Union[str, Sequence[str], None] = "f4d8a1c60b27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Zárolás-biztosan: a deploy alatt a régi példány még olvassa a táblát
    # (lásd app/core/migracio.py).
    zarasbiztos_ddl(
        op,
        lambda: op.add_column(
            "performance_certificates",
            sa.Column("szamla_kihagyva", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        leiras="performance_certificates.szamla_kihagyva",
    )
    zarasbiztos_ddl(
        op,
        lambda: op.add_column(
            "performance_certificates", sa.Column("szamla_kihagyas_oka", sa.Text(), nullable=True)
        ),
        leiras="performance_certificates.szamla_kihagyas_oka",
    )


def downgrade() -> None:
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("performance_certificates", "szamla_kihagyas_oka"),
        leiras="performance_certificates.szamla_kihagyas_oka (törlés)",
    )
    zarasbiztos_ddl(
        op,
        lambda: op.drop_column("performance_certificates", "szamla_kihagyva"),
        leiras="performance_certificates.szamla_kihagyva (törlés)",
    )
