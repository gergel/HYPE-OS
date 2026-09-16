"""Munkafelajánlás: az árazás kikerül - a jelentkezés nem tartalmaz összeget.

A munka_arajanlatok.osszeg nullable lesz: a felhasználó kérésére a külsős
csak azt jelzi, hogy érdekli és ráér; a díjazásról a kiválasztottal a
rendszeren kívül egyeznek meg. A régi (összeges) sorok érintetlenek.

Revision ID: c6u3t74q1s45
Revises: b5t2s63p0r44
"""

import sqlalchemy as sa
from alembic import op

revision = "c6u3t74q1s45"
down_revision = "b5t2s63p0r44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("munka_arajanlatok", "osszeg", existing_type=sa.Numeric(14, 2), nullable=True)


def downgrade() -> None:
    op.alter_column("munka_arajanlatok", "osszeg", existing_type=sa.Numeric(14, 2), nullable=False)
