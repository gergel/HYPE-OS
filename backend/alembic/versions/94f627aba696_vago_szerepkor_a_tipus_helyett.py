"""vago szerepkor a tipus helyett

Revision ID: 94f627aba696
Revises: 2b606b0ef643
Create Date: 2026-07-30 10:54:07.207252

Mostantól a SZEREPKÖR (role) mondja meg, ki vágó, a tipus pedig azt, hogy az
illető külsős vagy belsős - ez két külön kérdés, egy vágó ugyanúgy lehet
külsős, mint belsős.

Eddig a Notion-import a Vágók tábla relation-je alapján a tipus mezőt írta át
"vago"-ra, vagyis épp azt az információt törölte, hogy az illető külsős vagy
belsős volt-e. Ezért:

  1. akinek a tipus-a "vago", megkapja a "vago" szerepkört (adminokat és
     operátorokat kivéve - náluk ez jogvesztés lenne),
  2. a tipus-uk "kulsos" lesz, mert a régi érték már nem mond semmit a
     külsős/belsős kérdésről, és a vágók túlnyomó része külsős. Akinél ez
     tévedés, a személy adatlapján egy kattintással átállítható belsősre -
     és egy újabb Notion-import is helyreteszi, mert az importer a
     forrás-táblából veszi a tipust, és már nem írja felül.

A downgrade visszaállítja a tipus="vago" jelölést a vágó szerepkörűeknél, hogy
a régebbi kód (ami tipus alapján szűrt) is működjön.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94f627aba696'
down_revision: Union[str, Sequence[str], None] = '2b606b0ef643'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE employees
        SET role = 'vago'
        WHERE tipus = 'vago' AND role NOT IN ('admin', 'operator')
        """
    )
    op.execute("UPDATE employees SET tipus = 'kulsos' WHERE tipus = 'vago'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE employees SET tipus = 'vago' WHERE role = 'vago'")
