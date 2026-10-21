"""a felület témája emberenként

Világos/sötét nézet, a munkatárs rekordján tárolva - nem a böngészőben. Így a
választás az EMBERHEZ tartozik: aki otthon világosra állítja, az az irodai
gépen is világosat kap, és egy közös gépen a következő belépő nem örökli az
előző ízlését.

NULL = még nem választott; olyankor a sötét alap érvényes (a rendszer
szándékosan sötét alapú, ezért nincs automatikus igazodás az operációs
rendszer beállításához).

Revision ID: a7c2e40b95f1
Revises: f14d7ae5b209
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c2e40b95f1"
down_revision: Union[str, Sequence[str], None] = "f14d7ae5b209"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("tema", sa.String(length=10), nullable=True, comment="Felület témája: sotet / vilagos"),
    )


def downgrade() -> None:
    op.drop_column("employees", "tema")
