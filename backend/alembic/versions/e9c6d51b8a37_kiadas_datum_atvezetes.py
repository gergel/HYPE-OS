"""Kiadások: a fizetés dátuma átkerül a kiadás dátuma mezőbe.

A felhasználó kérése: ahol a fizetés dátuma ki van töltve, az az érték
kerüljön a kiadás dátuma mezőbe is - a Kiadások lista új "Dátum" oszlopa és
a projektkód-oldali kiadás-tábla is abból dolgozik, és a régi soroknál az
sokszor üres volt.

Csak az ÜRES kiadás-dátumot töltjük: ahol már van valódi kiadás-dátum (pl. a
Notion "Kiadás dátuma" mezőjéből), azt nem írjuk felül a fizetés napjával -
a kettő nem ugyanaz a nap, és a meglévő pontosabb adatot kár lenne
elveszteni. Ezért akárhányszor lefuttatható.

Revision ID: e9c6d51b8a37
Revises: d8e5b47c2f96
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e9c6d51b8a37"
down_revision = "d8e5b47c2f96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE expenses SET kiadas_datuma = fizetes_datuma "
            "WHERE fizetes_datuma IS NOT NULL AND kiadas_datuma IS NULL"
        )
    )


def downgrade() -> None:
    # Nem visszafordítható - nem tudni, melyik kiadás-dátum jött ebből.
    pass
