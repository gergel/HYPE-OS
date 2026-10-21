"""utomunka tabla kartya mezok

Az Utómunka "Vágó nézet" tábláján a kártyákon eddig fixen a határidő és a
kiosztott ember látszott. Ez a tábla írja le, mely mezők jelenjenek meg
rajtuk - egyetlen sor az egész rendszerre, mert a tábla mindenkinek ugyanaz.

Üres (nincs sor, vagy kartya_mezok NULL) esetén marad az eddigi
alapértelmezés, tehát a migráció önmagában semmit nem változtat a felületen.

Revision ID: 933a64e06321
Revises: f2e95bf24fae
Create Date: 2026-08-06 12:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '933a64e06321'
down_revision: Union[str, Sequence[str], None] = 'f2e95bf24fae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "deliverable_board_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kartya_mezok", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("deliverable_board_configs")
