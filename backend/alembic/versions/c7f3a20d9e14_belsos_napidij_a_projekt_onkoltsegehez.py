"""Belsős napidíj: mennyibe kerül a saját emberünk egy munkanapja

A projektek profitja eddig szebbnek látszott a valóságnál: a külsős stáb és az
utómunka pénzbe került, a belsős munkatárs munkája viszont ingyennek tűnt. Ez
az oszlop mondja meg, mennyibe kerül egy belsős munkanapja - innentől minden
forgatás költségébe beleszámít, amin az illető ott volt (lásd
services/belsos_koltseg.py és models/project_code.osszes_koltseg).

A vágóknál nincs jelentése: ők órabérben dolgoznak, a munkájuk ára a mért
időből jön.

FONTOS: ebből nem lesz Kiadás sor. A belsős alapbére a hónap végén, egyben
kerül a kiadások közé (Belsős TIG) - ha a napidíj is bekerülne, ugyanaz a pénz
kétszer szerepelne.

Revision ID: c7f3a20d9e14
Revises: b5e1a94c7d20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7f3a20d9e14"
down_revision: Union[str, Sequence[str], None] = "b5e1a94c7d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "napi_dij",
            sa.Numeric(12, 2),
            nullable=True,
            comment="Belsős napidíj - projekt-önköltséghez, NEM kiadás-sor",
        ),
    )


def downgrade() -> None:
    op.drop_column("employees", "napi_dij")
