"""A szeptember 1. előtti forgatások diszpó-állapotának újratöltése.

Ugyanaz a feltöltés, mint az a9e4c72d5b18-ban: a Notion projekt-import a
küldés-állapot mezőket (diszpo, elozetes_diszpo_kuldes) eddig újraírta a
Notion (üres) értékével, így az egyszer már beállított "Kiküldve" jelzések
egy-egy import után eltűntek. Az import ezeket a mezőket mostantól nem írja
(lásd notion_import/importers_wave2.py) - ez a migráció pedig visszateszi,
amit a korábbi importok letöröltek. Csak az ÜRES mezőket írja, ezért
akárhányszor lefuttatható.

Revision ID: f4b6d28a9c53
Revises: e8a3d95c7f14
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "f4b6d28a9c53"
down_revision = "e8a3d95c7f14"
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
    # Nem visszafordítható - nem tudni, melyik "Kiküldve" jött ebből.
    pass
