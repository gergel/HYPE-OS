"""Lara: a szamla@ levelezés olvasása bekapcsolva (tanulási forrás).

A felhasználó kérése: Lara olvassa a szamla@hypestab.hu postafiók összes
levelét a tanulás kezdete óta, és tanuljon belőlük. Ez csak OLVASÁS (Gmail
readonly) és tudás-JELÖLT készítése - üzleti rekordot nem módosít, ezért a
modul kikapcsolt állapota mellett is biztonságos. A Beállításokban
kikapcsolható („Levelezés olvasása"). Csak adat-módosítás, séma nem változik.

Revision ID: l5f2c63z0a74
Revises: k4e1b52y9z63
"""

from alembic import op

revision = "l5f2c63z0a74"
down_revision = "k4e1b52y9z63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A mező lehet SQL NULL vagy JSON null is - csak objektumhoz fűzünk.
    op.execute(
        "UPDATE aa_settings SET engedett_forrasok = "
        "(CASE WHEN jsonb_typeof(engedett_forrasok) = 'object' THEN engedett_forrasok ELSE '{}'::jsonb END)"
        " || '{\"levelezes\": true}'::jsonb WHERE id = 1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE aa_settings SET engedett_forrasok = engedett_forrasok - 'levelezes' "
        "WHERE id = 1 AND jsonb_typeof(engedett_forrasok) = 'object'"
    )
