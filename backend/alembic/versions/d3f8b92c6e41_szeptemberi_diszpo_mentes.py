"""A szeptemberi forgatások kitörölt diszpó-állapotának mentése.

Az f4b6d28a9c53 adat-javítás csak a 2026. szeptember 1. ELŐTTI forgatások
"Kiküldve" jelzését töltötte vissza - csakhogy a diszpó napokkal a forgatás
ELŐTT megy ki: az augusztus végén, már a HYPE OS-ből kiküldött, de SZEPTEMBERI
forgatásokra szóló diszpók állapotát ugyanúgy törölte a (ma már javított)
Notion-import, és azokat semmi nem állította helyre.

A bizonyíték a `gmail_thread_id`: ezt a küldés írja a projektre (lásd
services/dispo.py) - ahol ez ki van töltve, ott ténylegesen ment ki diszpó
levél. Az ELŐZETES állapotot töltjük vissza belőle (a szál a szokásos
munkamenetben az előzetessel indul); a TELJES diszpót szándékosan nem
találgatjuk - egy téves "Kiküldve" miatt a stáb soha nem kapná meg a valódi
diszpót.

Csak az ÜRES mezőt írja, ezért akárhányszor lefuttatható.

Revision ID: d3f8b92c6e41
Revises: c9d2e74a5f18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3f8b92c6e41"
down_revision = "c9d2e74a5f18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE projects SET elozetes_diszpo_kuldes = 'Kiküldve' "
            "WHERE forgatas_datuma >= '2026-09-01' "
            "AND gmail_thread_id IS NOT NULL AND gmail_thread_id <> '' "
            "AND (elozetes_diszpo_kuldes IS NULL OR elozetes_diszpo_kuldes = '')"
        )
    )


def downgrade() -> None:
    # Nem visszafordítható - nem tudni, melyik "Kiküldve" jött ebből.
    pass
