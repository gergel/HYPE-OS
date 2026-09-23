"""Lara: a teljes rendszer figyelése bekapcsolva (tanulási forrás).

A felhasználó kérése: Lara lássa át és figyelje az egész rendszert, és
tanuljon belőle — feladatot továbbra is csak adminisztrációs területen végez
(lásd admin_agent/rendszer.py, enums.ADMIN_FELADATTIPUSOK). Csak olvasás és
Lara saját tudás-táblái; a Beállításokban kikapcsolható („Teljes rendszer
figyelése"). Csak adat-módosítás.

Revision ID: o8i5f96c3d07
Revises: n7h4e85b2c96
"""

from alembic import op

revision = "o8i5f96c3d07"
down_revision = "n7h4e85b2c96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE aa_settings SET engedett_forrasok = "
        "(CASE WHEN jsonb_typeof(engedett_forrasok) = 'object' THEN engedett_forrasok ELSE '{}'::jsonb END)"
        " || '{\"rendszer\": true}'::jsonb WHERE id = 1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE aa_settings SET engedett_forrasok = engedett_forrasok - 'rendszer' "
        "WHERE id = 1 AND jsonb_typeof(engedett_forrasok) = 'object'"
    )
