"""kihagyás oka, és a "van már kész szerződés" lezárás

Két, egymáshoz tartozó igény:

1. Ha kihagyunk valakit a szerződésből vagy a TIG-ből, azt indokolni kell -
   fél év múlva senki nem fogja fejből tudni, miért maradt el egy papír.
2. Van, akinek MÁR van kész, feltöltött szerződése (jellemzően a Notionból
   áthozott sorok), a rendszer mégis kéri. Ez nem "kihagyás": a papír létezik,
   csak nem itt készült. Ezt külön állapot jelöli, nem a "Kihagyva" - az
   utóbbi azt jelentené, hogy egyáltalán nincs szerződés.

Az állapot maga szöveges oszlop (szerzodes_allapota), ezért a 2. ponthoz nem
kell séma-változás - csak az új oszlopok kellenek az indokláshoz.

Revision ID: d5e91c74a3b8
Revises: c8a4f2b91d37
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e91c74a3b8"
down_revision: Union[str, Sequence[str], None] = "c8a4f2b91d37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("kihagyas_oka", sa.Text(), nullable=True))
    op.add_column("performance_certificates", sa.Column("kihagyas_oka", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("performance_certificates", "kihagyas_oka")
    op.drop_column("contracts", "kihagyas_oka")
