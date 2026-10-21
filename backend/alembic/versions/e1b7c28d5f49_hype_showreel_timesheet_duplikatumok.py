"""HYPE showreel: duplikált vágási idő sorok törlése (a felhasználó kérése).

A showreel anyag(ok) munkaidő-elszámolásában ugyanaz a mérés többször szerepel
(jellemzően a Notion Timesheet Public/Private párosból jött be mindkettő, a
párosítás bevezetése előtt). Az UGYANAKKOR INDÍTOTT és UGYANOLYAN HOSSZÚ
sorokból egyet hagyunk meg (a legkisebb id-jűt), a többit töröljük - így a
vágással töltött idő és a belőle számolt költség sem duplázódik.

Csak a showreel nevű anyagok sorait érinti, és azokból is kizárólag a
tényleges duplikátumokat (azonos anyag + vágó + kezdés + perc + befejezés).

Revision ID: e1b7c28d5f49
Revises: d8f5e96b3c27
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "e1b7c28d5f49"
down_revision = "d8f5e96b3c27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    eredmeny = bind.execute(
        sa.text(
            """
            DELETE FROM timesheets
            WHERE id IN (
                SELECT id FROM (
                    SELECT t.id,
                           ROW_NUMBER() OVER (
                               PARTITION BY t.deliverable_id, t.employee_id,
                                            t.start_date, t.time_minutes, t.end_date
                               ORDER BY t.id
                           ) AS sorszam
                    FROM timesheets t
                    JOIN deliverables d ON d.id = t.deliverable_id
                    WHERE d.projekt_neve ILIKE '%showreel%'
                      AND t.start_date IS NOT NULL
                ) sorszamozott
                WHERE sorszam > 1
            )
            """
        )
    )
    print(f"HYPE showreel: {eredmeny.rowcount} duplikált munkaidő-sor törölve.")


def downgrade() -> None:
    # A törölt duplikátumok nem állíthatók vissza - nem is kellene: ugyanazok
    # a mérések voltak többszörözve.
    pass
