"""Autó karosszéria-típusa (az állapotfotók körvonalához).

A felhasználó kérése: az állapotfotó feltöltésekor az adott autó körvonala
látszódjon (mint a MOL Limónál), és arra rányomva kelljen kiválasztani,
melyik részéről készül a kép. A körvonal a karosszériától függ
(személyautó / SUV / kisbusz-furgon). Új, üres oszlop - üresen a típusnévből
ismeri fel a rendszer. Meglévő adat nem változik. Visszafordítható.

Revision ID: m3k4a5r6o7s8
Revises: l2a3u4t5o6f7
"""

import sqlalchemy as sa
from alembic import op

revision = "m3k4a5r6o7s8"
down_revision = "l2a3u4t5o6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("autok", sa.Column("karosszeria", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("autok", "karosszeria")
