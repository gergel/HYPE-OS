"""importalt idomeresek lezarasa

A Notionból áthozott munkaidő-mérések egy része nyitva (end_date=NULL)
maradt, és a felület ezeket ÉPP FUTÓ mérésként mutatta: napokban mért,
több százezer forintra ketyegő órákkal az Utómunka oldalon. Egy importált,
évekkel ezelőtti sor sosem lehet "épp fut" - ez a migráció lezárja őket.

A lezárás időpontja: kezdés + a Notionból hozott mért idő (Time (minutes)),
annak híján maga a kezdés (nulla perc - nem tudjuk, meddig tartott, de
tovább semmiképp nem ketyeghet). Csak azokat a sorokat érinti, amik a Notion
importból származnak (van hozzájuk notion_import_map sor) - egy most, a
rendszerben elindított, valóban futó mérőt nem zár le.

Revision ID: 49c37444b7f4
Revises: 1a04224ec881
Create Date: 2026-08-05 15:37:39.948255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49c37444b7f4'
down_revision: Union[str, Sequence[str], None] = '1a04224ec881'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE timesheets AS t
        SET end_date = t.start_date
            + (COALESCE(GREATEST(t.time_minutes, 0), 0) || ' minutes')::interval
        WHERE t.end_date IS NULL
          AND t.start_date IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM notion_import_map m
              WHERE m.entity_type = 'Timesheet' AND m.entity_id = t.id
          )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Nincs visszaút: a lezárás előtti állapot (end_date=NULL) épp a hibás
    # állapot volt, és nem is lenne megkülönböztethető azoktól a soroktól,
    # amiket az import eleve lezárva hozott be.
    pass
