"""keretszerzodes jelolo a contracts tablan

A projekt nélküli, alvállalkozói szerződés-sorok eddig egy kalap alá estek,
pedig kétfélék:

- akik a Notion "Alvállakozó keretszerződés (külsős)" táblájából jöttek: ezek
  a valódi, álló KERETSZERZŐDÉSEK - ezek mentesítenek a projektenkénti eseti
  szerződés alól, és csak ezek látszanak a Keretszerződések fülön;
- akik a "Külsős és belsős" tábla emberei mellől jöttek (cégadat + a saját
  lapjukon lévő aláírt PDF): ezek ESETI megbízási szerződések.

A megkülönböztetés eddig heurisztika volt (van-e állapot / aláírt papír),
ami az összes külsőst a keretszerződések közé sodorta. Ez az oszlop kimondja.

Visszatöltés: keretszerződés az, aminek KI VAN TÖLTVE a szerződés állapota. A
keretszerződés-tábla importja mindig beír állapotot ("Aktív", ha a Notionban
nincs), a kézi felvétel is; a munkatárs lapjáról jövő sorokba viszont sosem
kerül. Ráadásként a Notion-ból közvetlenül leképzett sorokat (notion_import_map)
és a velük azonos adószámú társ-sorokat is keretszerződésnek jelöljük - ezek a
"ketten szerződnek ugyanarra a cégre" esetek.

Revision ID: 4571c059cbef
Revises: 933a64e06321
Create Date: 2026-08-06 18:12:44.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4571c059cbef'
down_revision: Union[str, Sequence[str], None] = '933a64e06321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Amit keretszerződésnek tekintünk a meglévő adatban (lásd a modul docstringjét).
ALLO_KERETSZERZODES = """
    tipus = 'alvallalkozoi'
    AND project_id IS NULL
    AND (
        (szerzodes_allapota IS NOT NULL AND szerzodes_allapota <> '')
        OR id IN (
            SELECT entity_id FROM notion_import_map WHERE entity_type = 'Contract'
        )
    )
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "contracts",
        sa.Column("keretszerzodes", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(f"UPDATE contracts SET keretszerzodes = TRUE WHERE {ALLO_KERETSZERZODES}")
    # Társ-sorok: ugyanarra a cégre (adószám) ketten is szerződhetnek, és a
    # második ember sora már nem a Notion-lapról jött, hanem másolat (lásd
    # notion_import/importers.py _tarsult_keretszerzodes).
    op.execute(
        """
        UPDATE contracts AS c
        SET keretszerzodes = TRUE
        FROM contracts AS minta
        WHERE c.tipus = 'alvallalkozoi'
          AND c.project_id IS NULL
          AND c.keretszerzodes IS FALSE
          AND c.adoszam IS NOT NULL
          AND c.adoszam <> ''
          AND minta.keretszerzodes IS TRUE
          AND minta.adoszam = c.adoszam
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("contracts", "keretszerzodes")
