"""koltseg visszamenoleges kitoltese a mostani oraberekkel

Revision ID: f84bc9c23580
Revises: 94f627aba696
Create Date: 2026-07-30 11:41:26.840854

A vágási költség MINDIG a sor saját, befagyasztott órabéréből
(Timesheet.akkori_orabere) számolódik - ha valaki később többet keres, az a
régi költségeket nem írhatja át. Sok régi (és a Notionből importált) sornál
viszont sem az akkori órabér, sem a költség nincs kitöltve, így azok a
Pénzügyben 0 Ft-tal szerepelnek.

Ez a migráció ezeket a hiányzó értékeket tölti ki a MOSTANI órabérekkel
(Rate.orabler), és csak azokat:

  1. akkori_orabere <- a munkatárs mostani órabére, ahol eddig üres volt,
  2. koltseg <- perc/60 * akkori_orabere, ahol eddig üres volt.

Ahol már van kitöltött érték, ahhoz nem nyúl. A percet a time_minutes adja,
ennek hiányában a kezdés és a vége különbsége.

A downgrade nem állítja vissza - a migráció után nem különböztethető meg,
melyik érték volt eredetileg üres. Ez adat-visszatöltés, nem sémaváltozás:
visszafelé is működőképes marad az adatbázis.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f84bc9c23580'
down_revision: Union[str, Sequence[str], None] = '94f627aba696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Munkatársanként egy órabér: ha több Rate sora is van, a LEGUTÓBBI
    # (legnagyobb id) - ugyanaz, amit a futó kód is használ (lásd
    # services/deliverable_actions.aktualis_orabere).
    op.execute(
        """
        UPDATE timesheets AS t
        SET akkori_orabere = r.orabler
        FROM (
            SELECT DISTINCT ON (employee_id) employee_id, orabler
            FROM rates
            WHERE orabler IS NOT NULL
            ORDER BY employee_id, id DESC
        ) AS r
        WHERE r.employee_id = t.employee_id
          AND t.akkori_orabere IS NULL
        """
    )
    op.execute(
        """
        UPDATE timesheets
        SET koltseg = ROUND(
            (COALESCE(
                time_minutes,
                (EXTRACT(EPOCH FROM (end_date - start_date)) / 60)::numeric
            ) / 60) * akkori_orabere,
            2
        )
        WHERE koltseg IS NULL
          AND akkori_orabere IS NOT NULL
          -- Az ÉPP FUTÓ mérést kihagyjuk: annak a költségét a leállítás
          -- számolja ki (addig a felület percenként becsüli).
          AND NOT (start_date IS NOT NULL AND end_date IS NULL)
          AND (
              time_minutes IS NOT NULL
              OR (start_date IS NOT NULL AND end_date IS NOT NULL)
          )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Szándékosan nem csinál semmit: a kitöltött órabér/költség után már nem
    # megállapítható, melyik mező volt eredetileg üres, és a régi kód is
    # elboldogul a kitöltött értékekkel.
    pass
