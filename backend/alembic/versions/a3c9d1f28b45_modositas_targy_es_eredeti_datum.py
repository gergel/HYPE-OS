"""Szerződésmódosítás: a megbízás tárgya és az eredeti szerződés dátuma

A sablonba három kitöltendő mező került: a módosítás keltezése (az már megvolt),
a megbízás tárgya, és hogy mikor jött létre az EREDETI szerződés - a módosítás
szövege ezekre hivatkozik vissza. Mindkét új adat pillanatképként kerül a sorra,
mint a többi papíradat: ha a kereten később átírják a megbízás tárgyát, a már
kiküldött módosításon attól még az marad, ami rajta van.

Revision ID: a3c9d1f28b45
Revises: f1b8c2e40a67
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3c9d1f28b45"
down_revision: Union[str, Sequence[str], None] = "f1b8c2e40a67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("keret_modositasok", sa.Column("megbizas_targya", sa.String(length=255), nullable=True))
    op.add_column("keret_modositasok", sa.Column("szerzodes_letrejotte", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("keret_modositasok", "szerzodes_letrejotte")
    op.drop_column("keret_modositasok", "megbizas_targya")
