"""Diszpó PDF a saját tárhelyen (R2).

A felhasználó kérése: a stábtagok a diszpó PDF-jét ne a Drive-ról, hanem a
rendszer saját tárhelyéről (R2) nyissák meg. A kiküldés mostantól oda is
feltölti (services/dispo.py); a régi, csak Drive-linkes diszpók az első
megnyitáskor kerülnek át (routes/dashboard.sajat_diszpo_pdf_url).

Revision ID: c7e4d83f1a95
Revises: b6f3c72d9e84
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7e4d83f1a95"
down_revision = "b6f3c72d9e84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("diszpo_pdf_r2_url", sa.String(length=500), nullable=True))
    op.add_column("projects", sa.Column("diszpo_pdf_r2_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "diszpo_pdf_r2_key")
    op.drop_column("projects", "diszpo_pdf_r2_url")
