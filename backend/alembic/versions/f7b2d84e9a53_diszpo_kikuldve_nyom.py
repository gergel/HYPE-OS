"""Kitörölhetetlen nyom a diszpó-küldésről.

A "Kiküldve" jelzés többször is eltűnt élesben: a szöveges
diszpo/elozetes_diszpo_kuldes mezőket külső folyamat (a korábban javított
Notion-import, felülíró módban) újra és újra kiürítette. A szöveges mező
helyett ezért a küldés ténye mostantól SAJÁT tükör-oszlopba is beíródik
(elozetes_kikuldve_at / diszpo_kikuldve_at - lásd services/dispo.py), amihez
a küldésen kívül semmi nem nyúl; a felület a szöveges mezőt ebből pótolja,
ha az kiürült (lásd schemas/project.py). Ugyanaz a minta, mint a
naptar_datum_vege tükör-oszlopa.

A feltöltés: ahol MOST "Kiküldve" áll, ott a nyomot is beírjuk (a pontos
küldési idő nem ismert - a mostani időpont kerül be, a jelzésnek a TÉNY kell,
nem az időpont).

Revision ID: f7b2d84e9a53
Revises: e5a7c31d8f92
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7b2d84e9a53"
down_revision = "e5a7c31d8f92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("elozetes_kikuldve_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("diszpo_kikuldve_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE projects SET elozetes_kikuldve_at = NOW() "
            "WHERE elozetes_diszpo_kuldes = 'Kiküldve' AND elozetes_kikuldve_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE projects SET diszpo_kikuldve_at = NOW() "
            "WHERE diszpo = 'Kiküldve' AND diszpo_kikuldve_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("projects", "diszpo_kikuldve_at")
    op.drop_column("projects", "elozetes_kikuldve_at")
