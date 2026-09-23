"""Lara: az AI asszisztens figyelése bekapcsolva (tanulási forrás).

A felhasználó kérése: Lara figyelje, mit kérnek az AI asszisztenstől és mit
csinál meg, és tanuljon belőle. Ez csak OLVASÁS (az asszisztens táblái) és
tudás-JELÖLT készítése - üzleti rekordot nem módosít. A Beállításokban
kikapcsolható („AI asszisztens figyelése"). Csak adat-módosítás.

Revision ID: m6g3d74a1b85
Revises: l5f2c63z0a74
"""

from alembic import op

revision = "m6g3d74a1b85"
down_revision = "l5f2c63z0a74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A mező lehet SQL NULL vagy JSON null is - csak objektumhoz fűzünk.
    op.execute(
        "UPDATE aa_settings SET engedett_forrasok = "
        "(CASE WHEN jsonb_typeof(engedett_forrasok) = 'object' THEN engedett_forrasok ELSE '{}'::jsonb END)"
        " || '{\"asszisztens\": true}'::jsonb WHERE id = 1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE aa_settings SET engedett_forrasok = engedett_forrasok - 'asszisztens' "
        "WHERE id = 1 AND jsonb_typeof(engedett_forrasok) = 'object'"
    )
