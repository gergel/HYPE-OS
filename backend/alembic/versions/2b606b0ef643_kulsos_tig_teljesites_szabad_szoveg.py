"""kulsos tig teljesites szabad szoveg

Revision ID: 2b606b0ef643
Revises: d7d3b931c6cc
Create Date: 2026-07-30 10:15:35.573404

A Külsős TIG teljesítési ideje szabad szöveg lesz (nem tól-ig dátum). A
meglévő bejegyzésekhez ugyanabban a formában töltjük fel, ahogy eddig a
dokumentumba került ("2026.07.06." vagy "2026.07.06. - 2026.07.08."), hogy a
korábban rögzített adat ne vesszen el, és a felületen is az jelenjen meg.

A régi dátum-oszlopok maradnak: a downgrade így adatvesztés nélkül visszaáll.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b606b0ef643'
down_revision: Union[str, Sequence[str], None] = 'd7d3b931c6cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "performance_certificates",
        sa.Column("teljesites_szoveg", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE performance_certificates
        SET teljesites_szoveg = CASE
            WHEN teljesites_kezdete IS NOT NULL
                 AND teljesites_vege IS NOT NULL
                 AND teljesites_vege <> teljesites_kezdete
                THEN to_char(teljesites_kezdete, 'YYYY.MM.DD.') || ' - ' || to_char(teljesites_vege, 'YYYY.MM.DD.')
            WHEN teljesites_kezdete IS NOT NULL
                THEN to_char(teljesites_kezdete, 'YYYY.MM.DD.')
            WHEN teljesites_vege IS NOT NULL
                THEN to_char(teljesites_vege, 'YYYY.MM.DD.')
            ELSE NULL
        END
        WHERE teljesites_szoveg IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("performance_certificates", "teljesites_szoveg")
