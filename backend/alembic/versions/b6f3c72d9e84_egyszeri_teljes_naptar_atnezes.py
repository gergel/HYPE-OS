"""EGYSZERI teljes naptár-átnézés kérése (2026. szeptember).

A felhasználó kérése: a szinkron egyszer nézze át a TELJES naptárat (2026.
január 1-től), vesse össze a rendszerrel, és ami nincs benne, azt hozza be.
A migráció a szinkron-állapotba a jelölő-tokent írja (lásd
services/google_calendar.EGYSZERI_TELJES_TOKEN) - a deploy utáni első
percenkénti kör ettől széles, teljes átnézést futtat, majd a Google friss
sync tokenje felülírja a jelölőt, tehát a dolog magától egyszeri marad.

Revision ID: b6f3c72d9e84
Revises: a5e2b61c8d73
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b6f3c72d9e84"
down_revision = "a5e2b61c8d73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE calendar_sync_state SET sync_token = 'TELJES-ATNEZES-2026-09'"))


def downgrade() -> None:
    # A jelölő visszavonása: sima teljes szinkron jön a következő körben.
    op.execute(sa.text("UPDATE calendar_sync_state SET sync_token = NULL"))
