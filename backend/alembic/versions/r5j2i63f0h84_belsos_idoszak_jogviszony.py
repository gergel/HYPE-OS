"""Belsős időszakonként külön jogviszony (megbízás vagy alkalmazott).

A munkatárs adatlapján eddig EGY kapcsoló mondta meg, hogy megbízással
számláz-e vagy bejelentett alkalmazott - pedig ez időben változhat: aki 2026
nyaráig megbízással dolgozott, majd bejelentették, annál a régi hónapokra
TIG-et kell várni, az újakra csak a fizetés beírását. Ezért mostantól minden
belsős időszak külön hordozhatja a jogviszonyát (a felhasználó kérése).

A mező NULL-ozható, és a meglévő sorokat NEM töltjük ki: NULL = a munkatárs
adatlapján beállított alapértelmezés érvényes, tehát a migráció önmagában
senkinél semmin nem változtat. A meglévő `belsos_jogviszony` enum típust
használjuk újra.

Revision ID: r5j2i63f0h84
Revises: q4i1h52e9g73
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r5j2i63f0h84"
down_revision = "q4i1h52e9g73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "belsos_idoszakok",
        sa.Column(
            "jogviszony",
            postgresql.ENUM("megbizas", "alkalmazott", name="belsos_jogviszony", create_type=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("belsos_idoszakok", "jogviszony")
