"""Portál feltöltő link: ki mit töltött fel.

A felhasználó kérése: a feltöltő linken mindenki csak a SAJÁT feltöltéseit
lássa, és azokból törölni is tudjon. A feltöltő böngészője egy véletlen
azonosítót küld; ennek a lenyomatát (sha256) tároljuk a mappán, videón és
képen (`feltolto_kulcs`). Az admin felületen feltöltöttnél üres. Új, üres
oszlopok - meglévő adat nem változik. Visszafordítható.

Revision ID: k1f2e3l4t5o6
Revises: j0m1r2e3m4a5
"""

import sqlalchemy as sa
from alembic import op

revision = "k1f2e3l4t5o6"
down_revision = "j0m1r2e3m4a5"
branch_labels = None
depends_on = None

_TABLAK = ("portal_folders", "portal_videos", "portal_images")


def upgrade() -> None:
    for tabla in _TABLAK:
        op.add_column(tabla, sa.Column("feltolto_kulcs", sa.String(length=64), nullable=True))
        op.create_index(f"ix_{tabla}_feltolto_kulcs", tabla, ["feltolto_kulcs"])


def downgrade() -> None:
    for tabla in _TABLAK:
        op.drop_index(f"ix_{tabla}_feltolto_kulcs", table_name=tabla)
        op.drop_column(tabla, "feltolto_kulcs")
