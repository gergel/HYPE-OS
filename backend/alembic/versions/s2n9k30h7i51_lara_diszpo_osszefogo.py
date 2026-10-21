"""Lara: diszpó (brief + technika) és összefogó feladattípus - bizalmi szint sorok.

Az új feladattípusok (`diszpo`, `osszefogo`) a legszigorúbb, L0 (árnyék)
szinten kerülnek a bizalmi táblába, hogy a Beállításokban látszódjanak és
csak a jogosult ember emelhesse. Meglévő sorhoz nem nyúl (ON CONFLICT DO
NOTHING); séma-változás nincs.

Revision ID: s2n9k30h7i51
Revises: r1m8j29g6h40
"""

from alembic import op

revision = "s2n9k30h7i51"
down_revision = "r1m8j29g6h40"
branch_labels = None
depends_on = None

_TIPUSOK = ("diszpo", "osszefogo")


def upgrade() -> None:
    for tipus in _TIPUSOK:
        op.execute(
            "INSERT INTO aa_trust_policies (tipus, altipus, szint, created_at, updated_at) "
            f"SELECT '{tipus}', NULL, 'L0', now(), now() "
            f"WHERE NOT EXISTS (SELECT 1 FROM aa_trust_policies WHERE tipus = '{tipus}' AND altipus IS NULL)"
        )


def downgrade() -> None:
    # Csak az érintetlen (L0) sorokat vesszük vissza - egy ember által emelt
    # szintet nem törlünk némán.
    for tipus in _TIPUSOK:
        op.execute(f"DELETE FROM aa_trust_policies WHERE tipus = '{tipus}' AND altipus IS NULL AND szint = 'L0'")
