"""utomunka vagas leallitva idopont

Az utómunkán nyilvántartjuk, mikor állították le utoljára a vágás időmérőjét.
Az adat forrása a Notion 'Timesheet Public' táblájának 'End Date' mezője (lásd
notion_import/importers_wave2.py), a rendszeren belül pedig a timer leállítása
írja (services/deliverable_actions.stop_timer).

A meglévő adatból is feltöltjük, ami már megvan: a munkaidő-sorok utolsó
lezárási időpontja utómunkánként. A következő Notion import ezt felülírja a
Timesheet Public szerinti (pontosabb, órára is kiterjedő) értékkel.

Revision ID: c8630595d772
Revises: 3a4d1e536deb
Create Date: 2026-08-04 15:48:40.109760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8630595d772'
down_revision: Union[str, Sequence[str], None] = '3a4d1e536deb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "deliverables",
        sa.Column(
            "vagas_leallitva",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Vágás leállítva (Timesheet End Date)",
        ),
    )
    op.execute(
        """
        UPDATE deliverables d
        SET vagas_leallitva = t.utolso_vege
        FROM (
            SELECT deliverable_id, MAX(end_date) AS utolso_vege
            FROM timesheets
            WHERE deliverable_id IS NOT NULL AND end_date IS NOT NULL
            GROUP BY deliverable_id
        ) t
        WHERE t.deliverable_id = d.id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("deliverables", "vagas_leallitva")
