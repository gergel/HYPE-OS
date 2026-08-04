"""naptar szin es nem diszponalando

A naptárból szinkronizált esemény színe, és az abból következő jelölés, hogy
az esemény meeting/helyszínbejárás - vagyis nincs mit diszponálni rajta (lásd
services/google_calendar.py). Meglévő projekteknél a jelölés False; a
következő naptár-szinkron tölti fel azoknál, amik színt kaptak a naptárban.

Revision ID: 6c7b340e83b9
Revises: c8630595d772
Create Date: 2026-08-04 16:04:19.702288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c7b340e83b9'
down_revision: Union[str, Sequence[str], None] = 'c8630595d772'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("projects", sa.Column("naptar_szin", sa.String(length=30), nullable=True, comment="Naptár szín"))
    op.add_column(
        "projects",
        sa.Column(
            "nem_diszponalando",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Nem diszponálandó (meeting)",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "nem_diszponalando")
    op.drop_column("projects", "naptar_szin")
