"""szerzodes teljesites ideje szabad szoveg

Az alvállalkozói szerződésen a teljesítés ideje eddig kezdő+záró dátum volt.
A gyakorlatban nem mindig naptól-napig tartomány ("május 3-5.", "a projekt
teljes időtartama"), és a szerződésben pontosan az kell szerepeljen, amit
odaírnak - ezért egy szabad szöveges mező váltja. A meglévő dátumpárokból
feltöltjük a szöveget, hogy a régi szerződéseknél se tűnjön el az adat (a két
dátum-oszlop tartaléknak megmarad).

Revision ID: 2e4f22d51a5d
Revises: d2aafe7bd0bd
Create Date: 2026-08-06 06:06:59.207807

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e4f22d51a5d'
down_revision: Union[str, Sequence[str], None] = 'd2aafe7bd0bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "contracts",
        sa.Column("teljesites_szoveg", sa.String(length=255), nullable=True, comment="Teljesítés ideje - szabad szöveg"),
    )
    # A meglévő dátumpárok ugyanabban a formában, ahogy eddig a szerződésre
    # kerültek (lásd routes/subcontractor_contracts.py).
    op.execute(
        """
        UPDATE contracts
        SET teljesites_szoveg = CASE
            WHEN teljesites_vege IS NOT NULL AND teljesites_vege <> teljesites_kezdete
                THEN to_char(teljesites_kezdete, 'YYYY.MM.DD.') || ' - ' || to_char(teljesites_vege, 'YYYY.MM.DD.')
            ELSE to_char(teljesites_kezdete, 'YYYY.MM.DD.')
        END
        WHERE teljesites_kezdete IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("contracts", "teljesites_szoveg")
