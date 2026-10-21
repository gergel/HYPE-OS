"""A kiadás dátuma és a fizetés dátuma összevonása egyetlen mezőbe (a
felhasználó kérése). A megmaradó mező a `fizetes_datuma`; a régi
`kiadas_datuma` oszlop megszűnik.

Szabályok:
- Ahol a fizetes_datuma ki volt töltve, az számított eddig "kifizetettnek" a
  pénzügyi kimutatásokban - ezt a tényt átvisszük a `kesz` jelzőbe, mert
  mostantól a kimutatás a `kesz`-től függ, nem a dátum meglététől.
- Ahol a fizetes_datuma üres, de a kiadas_datuma ki volt töltve, a
  kiadas_datuma átkerül a fizetes_datuma-ba (megjelenítési dátumként) - a
  fizetes_datuma a mérvadó ott, ahol mindkettő megvolt.
- Végül a kiadas_datuma oszlop törlődik az expenses táblából (a kp_forgalmak
  tábla saját kiadas_datuma oszlopát NEM érinti).

Revision ID: f9x6w07t4u48
Revises: hype_preferences_20260921
"""

import sqlalchemy as sa
from alembic import op

revision = "f9x6w07t4u48"
down_revision = "hype_preferences_20260921"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) A jelenlegi "kifizetett" igazság átmentése a kesz jelzőbe: eddig a
    #    fizetes_datuma megléte jelentette a kifizetést a kimutatásokban.
    op.execute(
        "UPDATE expenses SET kesz = true "
        "WHERE fizetes_datuma IS NOT NULL AND (kesz IS NULL OR kesz = false)"
    )
    # 2) Összevonás: ahol nincs fizetes_datuma, de van kiadas_datuma, azt
    #    használjuk (a fizetes_datuma a mérvadó, ha mindkettő megvolt).
    op.execute(
        "UPDATE expenses SET fizetes_datuma = kiadas_datuma "
        "WHERE fizetes_datuma IS NULL AND kiadas_datuma IS NOT NULL"
    )
    # 3) A régi oszlop törlése (csak az expenses táblából).
    op.drop_column("expenses", "kiadas_datuma")


def downgrade() -> None:
    # Az oszlop visszaállítható, de a szétválasztott adat nem: a downgrade
    # üres kiadas_datuma oszlopot hoz vissza.
    op.add_column("expenses", sa.Column("kiadas_datuma", sa.Date(), nullable=True))
