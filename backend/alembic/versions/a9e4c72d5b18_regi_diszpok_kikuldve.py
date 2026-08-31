"""A 2026. szeptember 1. ELŐTTI forgatások diszpói kiküldöttnek jelölve.

A Notion-importból a "kiküldve" állapot nem jött át, ezért a felület a régi
(már rég kiküldött) diszpóknál is "Nincs kiküldve"-t mutatott. A felhasználó
kérése: visszamenőleg minden szeptember 1. előtti forgatás diszpója és
előzetes diszpója számítson kiküldöttnek - szeptember 1-től a rendszerből
megy a küldés, onnantól az állapot magától pontos.

Csak az ÜRES mezőket írjuk: ahol már áll valami (pl. a rendszerből küldve),
azt nem bántjuk. A dátum nélküli forgatásokat sem: azokról nem tudjuk, hogy
a múltból valók-e.

Revision ID: a9e4c72d5b18
Revises: f3a8d51c7e29
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "a9e4c72d5b18"
down_revision = "f3a8d51c7e29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for mezo in ("diszpo", "elozetes_diszpo_kuldes"):
        op.execute(
            sa.text(
                f"UPDATE projects SET {mezo} = 'Kiküldve' "
                f"WHERE forgatas_datuma < '2026-09-01' AND ({mezo} IS NULL OR {mezo} = '')"
            )
        )


def downgrade() -> None:
    # Nem visszafordítható: nem tudjuk megkülönböztetni, melyik "Kiküldve"
    # jött ebből a feltöltésből és melyik valódi küldésből.
    pass
