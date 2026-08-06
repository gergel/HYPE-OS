"""korlatozott anyag hozzaferes

Egy munkatárs hozzáférése leszűkíthető KONKRÉT utómunka-anyagokra: kap egy
fiókot, amivel a saját anyagán tudja indítani/leállítani az időmérőt és látja
a feladatát, de a többi projektünkbe nem lát bele. Ez a külsős vágóknál kell,
akiket egy-egy anyagra hívunk be.

NULL (és a hiányzó config-sor) = nincs szűkítés, minden anyagot lát - a
meglévő felhasználók viselkedése tehát változatlan.

Revision ID: 34e707b55613
Revises: ea6d72c343c3
Create Date: 2026-08-06 10:21:54.488791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34e707b55613'
down_revision: Union[str, Sequence[str], None] = 'ea6d72c343c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "page_access_configs",
        sa.Column(
            "lathato_deliverable_idk",
            sa.JSON(),
            nullable=True,
            comment="Csak ezeket az utómunka-anyagokat láthatja (None = mindet)",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("page_access_configs", "lathato_deliverable_idk")
