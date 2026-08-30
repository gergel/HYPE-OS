"""Kézi dátum-zár a projekteken

A projects.forgatas_datum_kezzel_beallitva oszlop: igaz, ha a forgatás
dátumait a HYPE OS felületén, KÉZZEL állították be. Amíg igaz, sem a
percenkénti naptár-szinkron, sem a Notion-import nem nyúlhat a dátum-
mezőkhöz (lásd models/project.py kommentje) - a felhasználó explicit
kérése: a kézzel beállított záró dátumot semmilyen automatizmus ne
törölhesse. Alapértelmezetten hamis (minden meglévő sort a szinkronok
kezelnek tovább, ahogy eddig).

Revision ID: e7f4c92ab1d3
Revises: c3d82a15b7e9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f4c92ab1d3"
down_revision: Union[str, Sequence[str], None] = "c3d82a15b7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "forgatas_datum_kezzel_beallitva",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Forgatás dátumai kézzel beállítva (szinkron nem írhatja felül)",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "forgatas_datum_kezzel_beallitva")
