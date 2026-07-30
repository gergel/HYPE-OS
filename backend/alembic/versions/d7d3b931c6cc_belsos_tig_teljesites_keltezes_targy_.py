"""belsos tig teljesites keltezes targy file_url

Revision ID: d7d3b931c6cc
Revises: e2c4615df1bb
Create Date: 2026-07-30 05:27:07.620215

A Belsős TIG kiegészül a teljesítés dátumával (ebből számoljuk, melyik hónapé
az igazolás - mindig az azt megelőző hónap), a keltezéssel, a TIG-enként
átírható megbízás tárgyával, és a kiküldött dokumentum Drive linkjével.

A meglévő sorokhoz visszamenőleg kitöltjük a teljesítés dátumát (a hónapot
követő hónap első napja) és a megbízás tárgyát (a munkatárs adatlapjáról),
hogy a régi bejegyzések se maradjanak üresen a felületen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7d3b931c6cc'
down_revision: Union[str, Sequence[str], None] = 'e2c4615df1bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "internal_performance_certificates",
        sa.Column("megbizas_targya", sa.String(length=255), nullable=True),
    )
    op.add_column("internal_performance_certificates", sa.Column("teljesites_datuma", sa.Date(), nullable=True))
    op.add_column("internal_performance_certificates", sa.Column("keltezes", sa.Date(), nullable=True))
    op.add_column("internal_performance_certificates", sa.Column("file_url", sa.String(length=500), nullable=True))

    op.execute(
        """
        UPDATE internal_performance_certificates
        SET teljesites_datuma = (make_date(ev, honap, 1) + INTERVAL '1 month')::date
        WHERE teljesites_datuma IS NULL
        """
    )
    op.execute(
        """
        UPDATE internal_performance_certificates AS c
        SET megbizas_targya = e.megbizas_targya
        FROM employees AS e
        WHERE e.id = c.employee_id AND c.megbizas_targya IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("internal_performance_certificates", "file_url")
    op.drop_column("internal_performance_certificates", "keltezes")
    op.drop_column("internal_performance_certificates", "teljesites_datuma")
    op.drop_column("internal_performance_certificates", "megbizas_targya")
