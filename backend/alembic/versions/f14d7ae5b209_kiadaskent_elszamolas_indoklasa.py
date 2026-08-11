"""a kiadásként elszámolás indoklása

A "projekt kiadásba kerül" jelölés önmagában csak annyit mond, hogy ettől az
embertől nem kell papír - azt nem, hogy hol keresd a pénzt. Ezért a jelöléshez
kötelező megadni, hova és miért került.

Külön oszlop a meglévő `megjegyzes`-től: azt a számlázó fél beállítása írja
(lásd routes/project_szamlazok.py set_szamlazo), és egy számlázó-módosítás
elfújná ezt a magyarázatot.

Revision ID: f14d7ae5b209
Revises: e2f83b160c94
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f14d7ae5b209"
down_revision: Union[str, Sequence[str], None] = "e2f83b160c94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("project_szamlazok", sa.Column("kiadas_megjegyzes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_szamlazok", "kiadas_megjegyzes")
