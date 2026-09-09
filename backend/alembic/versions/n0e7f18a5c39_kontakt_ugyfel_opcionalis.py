"""A megrendelői kontakt ügyfele opcionális (a felhasználó kérése): az
utómunka adatlapról helyben felvett új kontaktnál ne legyen kötelező
ügyfelet választani - a felületek ilyenkor ügyfélnév nélkül mutatják.

Revision ID: n0e7f18a5c39
Revises: m9d6e07f4b28
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "n0e7f18a5c39"
down_revision = "m9d6e07f4b28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("contacts", "client_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Csak akkor fut le, ha már nincs ügyfél nélküli kontakt - a NOT NULL
    # visszaállítása előtt azokat kézzel kell ügyfélhez kötni vagy törölni.
    op.alter_column("contacts", "client_id", existing_type=sa.Integer(), nullable=False)
