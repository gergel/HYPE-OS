"""normalize elozetes diszpo status to Kikuldve

Revision ID: 16e6352592d7
Revises: 90c71839b097
Create Date: 2026-07-25 18:36:02.911551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16e6352592d7'
down_revision: Union[str, Sequence[str], None] = '90c71839b097'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Csak adat: a korábban kiküldött előzetes diszpók "Küldésre állítva"
    állapota "Kiküldve"-re javul, hogy a régi és az új rekordok ugyanazt
    mutassák (lásd services/dispo.py send_elozetes_diszpo). A jelentés
    ugyanaz: ez az érték csak sikeres kiküldés után került be."""
    op.execute("UPDATE projects SET elozetes_diszpo_kuldes = 'Kiküldve' WHERE elozetes_diszpo_kuldes = 'Küldésre állítva'")


def downgrade() -> None:
    """Visszafelé nem különböztethető meg, melyik sor volt eredetileg
    "Küldésre állítva" és melyik "Kiküldve", ezért mindet visszaírjuk a régi
    szövegre - a jelentésük azonos, csak a felirat tér el."""
    op.execute("UPDATE projects SET elozetes_diszpo_kuldes = 'Küldésre állítva' WHERE elozetes_diszpo_kuldes = 'Kiküldve'")
