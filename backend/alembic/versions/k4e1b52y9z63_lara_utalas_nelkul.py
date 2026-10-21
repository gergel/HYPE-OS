"""Lara: az utalás kikerül a feladattípusok közül.

Lara utalni soha nem fog, és az utalás-előkészítés sem az ő dolga (a
felhasználó döntése): hogy mi utalható, azt a Pénzügyek „Utalásra váró
számlák" listája mutatja. Ezért:

- az `utalas` bizalmi szint sora törlődik (a Beállításokban ne legyen ilyen);
- a még nyitott utalás-feladatok VISSZAVONVA állapotba kerülnek, indokkal
  (nem törlődnek - a naplóban és a lezárt feladatok között megmaradnak).

Revision ID: k4e1b52y9z63
Revises: j3d0a41x8y52
"""

from alembic import op

revision = "k4e1b52y9z63"
down_revision = "j3d0a41x8y52"
branch_labels = None
depends_on = None

_INDOK = "Lara utalással nem foglalkozik — a kifizetendők a Pénzügyek „Utalásra váró számlák” listájában."


def upgrade() -> None:
    op.execute("DELETE FROM aa_trust_policies WHERE tipus = 'utalas'")
    op.execute(
        "UPDATE aa_tasks SET allapot = 'cancelled', blokkolo_ok = '"
        + _INDOK.replace("'", "''")
        + "' WHERE tipus = 'utalas' AND allapot NOT IN ('completed', 'rejected', 'cancelled')"
    )


def downgrade() -> None:
    # A bizalmi szint visszaáll (L0); a visszavont feladatok visszavontak maradnak.
    op.execute(
        "INSERT INTO aa_trust_policies (tipus, altipus, szint) "
        "SELECT 'utalas', NULL, 'L0' WHERE NOT EXISTS "
        "(SELECT 1 FROM aa_trust_policies WHERE tipus = 'utalas' AND altipus IS NULL)"
    )
