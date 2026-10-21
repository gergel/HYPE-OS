"""google oauth token diagnosztika (megujitas es hiba nyoma)

Revision ID: b3f7c1d92a04
Revises: e8c1b53f27a4
Create Date: 2026-08-21 12:00:00.000000

A naptár-szinkron hozzáférése eddig némán állt le: a tárolt token megléte
"Csatlakozva" állapotot jelentett, akkor is, ha a megújítás napok óta
elhasalt. Ez a három oszlop mondja meg, ÉL-E a kapcsolat, és ha nem, mióta és
miért (lásd services/google_oauth.load_credentials).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f7c1d92a04"
down_revision: Union[str, Sequence[str], None] = "e8c1b53f27a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("google_oauth_tokens", sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("google_oauth_tokens", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("google_oauth_tokens", sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("google_oauth_tokens", "last_error_at")
    op.drop_column("google_oauth_tokens", "last_error")
    op.drop_column("google_oauth_tokens", "last_refresh_at")
